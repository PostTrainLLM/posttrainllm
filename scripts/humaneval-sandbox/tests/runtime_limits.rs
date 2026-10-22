#![cfg(target_os = "macos")]

use std::fs;
use std::os::unix::fs::DirBuilderExt;
use std::process::Command;
use std::time::{SystemTime, UNIX_EPOCH};

fn run_candidate(code: &str, memory_mb: &str) -> serde_json::Value {
    let root = std::env::temp_dir().join(format!(
        "posttrainllm-budget-test-{}-{}",
        std::process::id(),
        SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap()
            .as_nanos()
    ));
    fs::DirBuilder::new().mode(0o700).create(&root).unwrap();
    let code_path = root.join("code.py");
    let test_path = root.join("test.py");
    fs::write(&code_path, code).unwrap();
    fs::write(
        &test_path,
        "def check(function):\n    assert function(0) == 81\n",
    )
    .unwrap();
    let output = Command::new(env!("CARGO_BIN_EXE_humaneval-sandbox"))
        .arg("--code")
        .arg(code_path)
        .arg("--test")
        .arg(test_path)
        .args(["--timeout", "1", "--memory-mb", memory_mb])
        .output()
        .unwrap();
    fs::remove_dir_all(root).unwrap();
    assert!(
        output.status.success(),
        "{}",
        String::from_utf8_lossy(&output.stderr)
    );
    serde_json::from_slice(&output.stdout).unwrap()
}

#[test]
fn normal_code_passes_with_measured_memory() {
    // Fast exits previously raced live RSS observation and failed valid code.
    for _ in 0..20 {
        let report = run_candidate("def candidate(_):\n    return 9 * 9\n", "256");
        assert_eq!(report["passed"], true, "{report}");
        assert!(report["max_owned_child_rss_bytes"].as_u64().unwrap() > 0);
        assert!(report["stop_reason"].is_null());
    }
}

#[test]
fn over_budget_allocation_cannot_be_scored_as_a_pass() {
    let report = run_candidate(
        "def candidate(_):\n    data = bytearray(64 * 1024 * 1024)\n    return 81 if data else 0\n",
        "32",
    );
    assert_eq!(report["passed"], false);
    assert_eq!(report["stop_reason"], "memory_limit");
    assert!(report["max_owned_child_rss_bytes"].as_u64().unwrap() > 32 * 1024 * 1024);
}

#[test]
fn verbose_output_is_bounded_without_a_pipe_deadlock() {
    let report = run_candidate(
        "def candidate(_):\n    print('x' * (128 * 1024))\n    return 81\n",
        "256",
    );
    assert_eq!(report["passed"], false);
    assert_eq!(report["stop_reason"], "output_limit");
    assert!(report["stdout"].as_str().unwrap().len() <= 64 * 1024);
    assert!(report["wall_seconds"].as_f64().unwrap() < 2.0);
}

#[test]
fn busy_code_cannot_outlive_the_cpu_and_wall_budgets() {
    let report = run_candidate("def candidate(_):\n    while True:\n        pass\n", "256");
    assert_eq!(report["passed"], false);
    assert!(report["wall_seconds"].as_f64().unwrap() < 3.0);
}
