use std::fs;
use std::io::{Read, Write};
use std::os::unix::fs::DirBuilderExt;
use std::os::unix::process::CommandExt;
use std::path::PathBuf;
use std::process::{Child, Command, Stdio};
use std::sync::{
    Arc,
    atomic::{AtomicBool, Ordering},
};
use std::time::{Duration, Instant, SystemTime, UNIX_EPOCH};

use anyhow::{Context, Result, ensure};
use clap::Parser;
use serde_json::json;

#[derive(Debug, Parser)]
#[command(about = "Run generated Python code plus tests with macOS sandbox-exec and rlimits")]
struct Args {
    #[arg(long)]
    code: PathBuf,
    #[arg(long)]
    test: PathBuf,
    #[arg(long, default_value_t = 10)]
    timeout: u64,
    #[arg(long, default_value_t = 256)]
    memory_mb: u64,
    #[arg(long, default_value_t = false)]
    allow_network: bool,
}

fn main() -> Result<()> {
    let args = Args::parse();
    ensure!(
        cfg!(target_os = "macos"),
        "This runner requires macOS sandbox-exec; no unsandboxed fallback is permitted"
    );
    ensure!(
        std::path::Path::new("/usr/bin/sandbox-exec").is_file(),
        "sandbox-exec is unavailable"
    );
    let python = PythonRuntime::discover()?;
    let started = Instant::now();
    let run_dir = std::env::temp_dir().join(format!(
        "posttrainllm-humaneval-{}-{}",
        std::process::id(),
        SystemTime::now().duration_since(UNIX_EPOCH)?.as_millis()
    ));
    fs::DirBuilder::new().mode(0o700).create(&run_dir)?;
    let run_dir = fs::canonicalize(run_dir)?;
    let runner = run_dir.join("runner.py");
    let code = fs::read_to_string(&args.code)
        .with_context(|| format!("could not read {}", args.code.display()))?;
    let test = fs::read_to_string(&args.test)
        .with_context(|| format!("could not read {}", args.test.display()))?;
    let mut f = fs::File::create(&runner)?;
    writeln!(f, "{code}")?;
    writeln!(f, "\n{test}")?;
    writeln!(f, "\nif __name__ == '__main__':\n    check(candidate)")?;

    let mut cmd = python_command(&run_dir, &python, args.allow_network);
    cmd.arg(&runner)
        .stdout(Stdio::piped())
        .stderr(Stdio::piped());

    let mem_bytes = args
        .memory_mb
        .checked_mul(1024 * 1024)
        .context("Invalid memory limit")?;
    ensure!(mem_bytes > 0, "Memory limit must be positive");
    unsafe {
        cmd.pre_exec(move || {
            set_limit(libc::RLIMIT_CPU, args.timeout, args.timeout + 1)?;
            let _ = set_limit(libc::RLIMIT_AS, mem_bytes, mem_bytes);
            #[cfg(target_os = "macos")]
            {
                let _ = set_limit(libc::RLIMIT_DATA, mem_bytes, mem_bytes);
            }
            set_limit(libc::RLIMIT_NOFILE, 64, 64)?;
            set_limit(libc::RLIMIT_FSIZE, 8 * 1024 * 1024, 8 * 1024 * 1024)?;
            Ok(())
        });
    }

    let report = run_sandbox(cmd, args.timeout, mem_bytes, started)?;
    println!("{report}");
    let _ = fs::remove_dir_all(&run_dir);
    Ok(())
}

fn run_sandbox(
    mut cmd: Command,
    timeout: u64,
    mem_bytes: u64,
    started: Instant,
) -> Result<serde_json::Value> {
    let mut child = cmd.spawn()?;
    // Drain both pipes concurrently. A verbose candidate must not deadlock
    // against a full pipe or cause unbounded parent-side output allocation.
    let overflow = Arc::new(AtomicBool::new(false));
    let stdout = capture_output(child.stdout.take().expect("piped stdout"), overflow.clone());
    let stderr = capture_output(child.stderr.take().expect("piped stderr"), overflow.clone());
    let deadline = Instant::now() + Duration::from_secs(timeout + 1);
    let (mut stop_reason, mut peak_rss_bytes) =
        monitor_child(&mut child, &overflow, deadline, mem_bytes, resident_bytes)?;
    let output = child.wait_with_output()?;
    let stdout = stdout.join().expect("stdout capture thread")?;
    let stderr = stderr.join().expect("stderr capture thread")?;
    // Darwin rlimits do not establish a resident-RAM ceiling. Include the
    // kernel's completed-child peak so even a fast over-budget exit fails.
    // This conservatively includes this invocation's trusted Python discovery.
    let mut usage: libc::rusage = unsafe { std::mem::zeroed() };
    ensure!(
        unsafe { libc::getrusage(libc::RUSAGE_CHILDREN, &mut usage) } == 0,
        "Cannot read completed-child memory usage"
    );
    peak_rss_bytes = peak_rss_bytes.max(usage.ru_maxrss.max(0) as u64);
    if peak_rss_bytes > mem_bytes {
        stop_reason = Some("memory_limit");
    } else if overflow.load(Ordering::SeqCst) {
        stop_reason = Some("output_limit");
    }
    let wall = started.elapsed().as_secs_f64();
    let passed = output.status.success() && stop_reason.is_none();
    Ok(json!({
        "passed": passed,
        "stdout": String::from_utf8_lossy(&stdout),
        "stderr": String::from_utf8_lossy(&stderr),
        "exit_code": output.status.code().unwrap_or(-1),
        "wall_seconds": wall,
        "stop_reason": stop_reason,
        "max_owned_child_rss_bytes": peak_rss_bytes,
        "memory_limit_bytes": mem_bytes,
        "memory_observation": "1ms live RSS polling plus kernel completed-child peak; polling can overshoot",
        "output_limit_bytes_per_stream": 64 * 1024
    }))
}

fn monitor_child(
    child: &mut Child,
    overflow: &AtomicBool,
    deadline: Instant,
    mem_bytes: u64,
    mut resident: impl FnMut(u32) -> std::io::Result<u64>,
) -> Result<(Option<&'static str>, u64)> {
    let mut stop_reason = None;
    let mut peak_rss_bytes = 0;
    let mut missing_samples = 0;
    loop {
        if child.try_wait()?.is_some() {
            break;
        }
        match resident(child.id()) {
            Ok(bytes) => {
                peak_rss_bytes = peak_rss_bytes.max(bytes);
                missing_samples = 0;
            }
            Err(_) if child.try_wait()?.is_some() => break,
            Err(_) => {
                // proc_pidinfo can lose an exiting process before waitpid sees
                // its exit. Retry at most three live samples; the completed
                // child's kernel peak below still governs pass eligibility.
                missing_samples += 1;
                if missing_samples >= 3 {
                    stop_reason = Some("memory_observation_failed");
                }
            }
        }
        if peak_rss_bytes > mem_bytes {
            stop_reason = Some("memory_limit");
        } else if overflow.load(Ordering::SeqCst) {
            stop_reason = Some("output_limit");
        } else if Instant::now() >= deadline {
            stop_reason = Some("timeout");
        }
        if stop_reason.is_some() {
            let _ = child.kill();
            break;
        }
        std::thread::sleep(Duration::from_millis(1));
    }
    Ok((stop_reason, peak_rss_bytes))
}

fn capture_output(
    reader: impl Read + Send + 'static,
    overflow: Arc<AtomicBool>,
) -> std::thread::JoinHandle<std::io::Result<Vec<u8>>> {
    std::thread::spawn(move || {
        let mut bytes = Vec::new();
        reader.take(64 * 1024 + 1).read_to_end(&mut bytes)?;
        if bytes.len() > 64 * 1024 {
            bytes.truncate(64 * 1024);
            overflow.store(true, Ordering::SeqCst);
        }
        Ok(bytes)
    })
}

#[cfg(target_os = "macos")]
fn resident_bytes(pid: u32) -> std::io::Result<u64> {
    // sys/proc_info.h: PROC_PIDTASKINFO = 4; six uint64 fields followed by
    // twelve int32 fields. Resident size is the second uint64, in bytes.
    #[repr(C)]
    struct TaskInfo {
        sizes_and_times: [u64; 6],
        counters: [i32; 12],
    }
    unsafe extern "C" {
        fn proc_pidinfo(
            pid: libc::c_int,
            flavor: libc::c_int,
            arg: u64,
            buffer: *mut libc::c_void,
            size: libc::c_int,
        ) -> libc::c_int;
    }
    let mut info: TaskInfo = unsafe { std::mem::zeroed() };
    let size = std::mem::size_of::<TaskInfo>() as libc::c_int;
    let read = unsafe {
        proc_pidinfo(
            pid as libc::c_int,
            4,
            0,
            (&mut info as *mut TaskInfo).cast(),
            size,
        )
    };
    if read == size {
        Ok(info.sizes_and_times[1])
    } else {
        Err(std::io::Error::last_os_error())
    }
}

#[cfg(not(target_os = "macos"))]
fn resident_bytes(_pid: u32) -> std::io::Result<u64> {
    Err(std::io::Error::other("Mac-only runner"))
}

struct PythonRuntime {
    executable: PathBuf,
    prefix: PathBuf,
}

impl PythonRuntime {
    fn discover() -> Result<Self> {
        // Resolve the installed developer runtime before entering the sandbox.
        // /usr/bin/python3 can be an xcrun launcher that writes outside the run.
        let output = Command::new("/usr/bin/python3")
            .args(["-I", "-S", "-c", "import json,sys; print(json.dumps({'executable':sys.executable,'prefix':sys.prefix}))"])
            .env_clear()
            .env("PATH", "/usr/bin:/bin")
            .output()?;
        ensure!(
            output.status.success(),
            "Installed isolated Python discovery failed"
        );
        let value: serde_json::Value = serde_json::from_slice(&output.stdout)?;
        let prefix = fs::canonicalize(value["prefix"].as_str().context("Missing Python prefix")?)?;
        // Apple's framework bin/python is itself a launcher. Run the underlying
        // interpreter so generated code never gets process-fork permission.
        let framework = prefix.join("Resources/Python.app/Contents/MacOS/Python");
        let executable = if framework.is_file() {
            fs::canonicalize(framework)?
        } else {
            fs::canonicalize(
                value["executable"]
                    .as_str()
                    .context("Missing Python executable")?,
            )?
        };
        ensure!(
            executable.starts_with(&prefix),
            "Python executable is outside its runtime prefix"
        );
        Ok(Self { executable, prefix })
    }
}

fn profile_path(path: &std::path::Path) -> String {
    serde_json::to_string(&path.to_string_lossy()).expect("path string serialization")
}

fn python_command(
    run_dir: &std::path::Path,
    python: &PythonRuntime,
    allow_network: bool,
) -> Command {
    let mut command = Command::new("/usr/bin/sandbox-exec");
    command
        .args(["-p", &sandbox_profile(run_dir, python, allow_network)])
        .arg(&python.executable)
        .args(["-I", "-S", "-B"])
        .env_clear()
        .env("PATH", "/usr/bin:/bin")
        .env("TMPDIR", run_dir)
        .current_dir(run_dir);
    command
}

fn sandbox_profile(
    run_dir: &std::path::Path,
    python: &PythonRuntime,
    allow_network: bool,
) -> String {
    let ancestors: std::collections::BTreeSet<_> =
        [&python.executable, &python.prefix, &run_dir.to_path_buf()]
            .into_iter()
            .flat_map(|path| path.ancestors().skip(1).map(PathBuf::from))
            .collect();
    let metadata = ancestors
        .iter()
        .map(|path| format!("(literal {})", profile_path(path)))
        .collect::<Vec<_>>()
        .join(" ");
    format!(
        r#"(version 1)
(deny default)
(allow process-exec (literal {exe}))
(allow file-read-metadata {metadata})
(allow file-read* (subpath {prefix}) (subpath "/System/Library") (subpath "/usr/lib")
  (subpath {dir}) (literal {exe}) (literal "/") (literal "/dev/null") (literal "/dev/urandom"))
{}
(allow file-write* (subpath {dir}))
(allow sysctl-read)
"#,
        if allow_network {
            "(allow network*)"
        } else {
            "(deny network*)"
        },
        exe = profile_path(&python.executable),
        prefix = profile_path(&python.prefix),
        dir = profile_path(run_dir),
    )
}

fn set_limit(resource: libc::c_int, soft: u64, hard: u64) -> std::io::Result<()> {
    let lim = libc::rlimit {
        rlim_cur: soft as libc::rlim_t,
        rlim_max: hard as libc::rlim_t,
    };
    let rc = unsafe { libc::setrlimit(resource, &lim) };
    if rc == 0 {
        Ok(())
    } else {
        Err(std::io::Error::last_os_error())
    }
}

#[cfg(all(test, target_os = "macos"))]
mod tests {
    use super::*;

    #[test]
    fn persistent_memory_observation_failure_stops_the_owned_child() -> Result<()> {
        let mut child = Command::new("/bin/sleep").arg("1").spawn()?;
        let mut samples = 0;
        let (reason, _) = monitor_child(
            &mut child,
            &AtomicBool::new(false),
            Instant::now() + Duration::from_secs(2),
            256 * 1024 * 1024,
            |_| {
                samples += 1;
                Err(std::io::Error::other(
                    "owned unavailable-observation fixture",
                ))
            },
        )?;
        assert!(!child.wait()?.success());
        assert_eq!(reason, Some("memory_observation_failed"));
        assert_eq!(samples, 3);
        Ok(())
    }

    #[test]
    fn runtime_policy_denies_owned_outside_files_network_and_children() -> Result<()> {
        let python = PythonRuntime::discover()?;
        let root =
            std::env::temp_dir().join(format!("posttrainllm-policy-test-{}", std::process::id()));
        fs::DirBuilder::new().mode(0o700).create(&root)?;
        let root = fs::canonicalize(root)?;
        let run = root.join("run");
        fs::create_dir(&run)?;
        let outside = root.join("owned-nonsecret-canary");
        fs::write(&outside, "owned nonsecret fixture")?;
        let listener = std::net::TcpListener::bind(("127.0.0.1", 0))?;
        let port = listener.local_addr()?.port();
        let source = format!(
            r#"import json,math,pathlib,socket,subprocess
results = {{'python_math': math.isqrt(81) == 9}}
pathlib.Path('scratch').write_text('allowed')
results['run_write'] = pathlib.Path('scratch').read_text() == 'allowed'
outside = pathlib.Path({outside})
def denied(name, action):
    try:
        action()
        results[name] = False
    except PermissionError:
        results[name] = True
denied('outside_read', outside.read_text)
denied('outside_write', lambda: outside.write_text('changed'))
pathlib.Path('link').symlink_to(outside)
denied('symlink_read', pathlib.Path('link').read_text)
denied('network', lambda: socket.create_connection(('127.0.0.1', {port}), timeout=1))
denied('child', lambda: subprocess.run(['/usr/bin/true'], check=True))
print(json.dumps(results))
"#,
            outside = profile_path(&outside),
        );
        let output = python_command(&run, &python, false)
            .args(["-c", &source])
            .output()?;
        // Cleanup only this test's newly created fixture, including its symlink.
        fs::remove_dir_all(&root)?;
        ensure!(
            output.status.success(),
            "Python control failed: {}",
            String::from_utf8_lossy(&output.stderr)
        );
        let results: serde_json::Value = serde_json::from_slice(&output.stdout)?;
        for control in [
            "python_math",
            "run_write",
            "outside_read",
            "outside_write",
            "symlink_read",
            "network",
            "child",
        ] {
            ensure!(
                results[control] == true,
                "Control failed: {control}: {results}"
            );
        }
        Ok(())
    }
}
