use std::fs;
use std::io::Write;
use std::os::unix::fs::DirBuilderExt;
use std::os::unix::process::CommandExt;
use std::path::PathBuf;
use std::process::{Command, Stdio};
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

    let profile = sandbox_profile(&run_dir, &python, args.allow_network);
    let mut cmd = Command::new("/usr/bin/sandbox-exec");
    cmd.args(["-p", &profile])
        .arg(&python.executable)
        .args(["-I", "-S", "-B"])
        .arg(&runner)
        .env_clear()
        .env("PATH", "/usr/bin:/bin")
        .env("TMPDIR", &run_dir)
        .current_dir(&run_dir)
        .stdout(Stdio::piped())
        .stderr(Stdio::piped());

    let mem_bytes = args.memory_mb * 1024 * 1024;
    unsafe {
        cmd.pre_exec(move || {
            set_limit(libc::RLIMIT_CPU, args.timeout, args.timeout + 1)?;
            let _ = set_limit(libc::RLIMIT_AS, mem_bytes, mem_bytes);
            #[cfg(target_os = "macos")]
            {
                let _ = set_limit(libc::RLIMIT_DATA, mem_bytes, mem_bytes);
            }
            set_limit(libc::RLIMIT_NOFILE, 64, 64)?;
            Ok(())
        });
    }

    let mut child = cmd.spawn()?;
    let deadline = Instant::now() + Duration::from_secs(args.timeout + 1);
    let timed_out;
    loop {
        if child.try_wait()?.is_some() {
            timed_out = false;
            break;
        }
        if Instant::now() >= deadline {
            let _ = child.kill();
            timed_out = true;
            break;
        }
        std::thread::sleep(Duration::from_millis(50));
    }
    let output = child.wait_with_output()?;
    let wall = started.elapsed().as_secs_f64();
    let stdout = String::from_utf8_lossy(&output.stdout).to_string();
    let stderr = String::from_utf8_lossy(&output.stderr).to_string();
    let passed = output.status.success() && !timed_out;
    println!(
        "{}",
        json!({
            "passed": passed,
            "stdout": stdout,
            "stderr": if timed_out { format!("{stderr}\ntimeout") } else { stderr },
            "exit_code": output.status.code().unwrap_or(-1),
            "wall_seconds": wall
        })
    );
    let _ = fs::remove_dir_all(&run_dir);
    Ok(())
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
        let output = Command::new("/usr/bin/sandbox-exec")
            .args(["-p", &sandbox_profile(&run, &python, false)])
            .arg(&python.executable)
            .args(["-I", "-S", "-B", "-c", &source])
            .env_clear()
            .env("PATH", "/usr/bin:/bin")
            .env("TMPDIR", &run)
            .current_dir(&run)
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
