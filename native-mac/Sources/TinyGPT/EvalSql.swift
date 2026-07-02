import Foundation
import TinyGPTModel

/// `tinygpt eval-sql` (B1, SQL domain) — execution-accuracy eval for a
/// text-to-SQL specialist. Self-contained: runs predicted vs gold SQL against
/// a SQLite DB via the `sqlite3` CLI and compares result sets (order-
/// insensitive) plus normalized exact-match. No model needed to score a
/// predictions file — generation (the GPU step) produces `predicted_sql`.
enum EvalSql {
    static func run(args: [String]) {
        var dataPath: String?, outPath: String?, dbDir: String?
        var i = 0
        while i < args.count {
            switch args[i] {
            case "--data":   dataPath = args[i+1]; i += 2
            case "--out":    outPath = args[i+1]; i += 2
            case "--db-dir": dbDir = args[i+1]; i += 2
            case "-h", "--help": exitUsage(0)
            default:
                if args[i].hasPrefix("-") { fputs("unknown flag: \(args[i])\n", stderr); exitUsage() }
                dataPath = args[i]; i += 1
            }
        }
        guard let dataPath = dataPath else { fputs("missing <preds.jsonl> (or --data)\n", stderr); exitUsage() }
        guard let raw = try? String(contentsOfFile: dataPath, encoding: .utf8) else {
            fputs("could not read \(dataPath)\n", stderr); exit(1)
        }
        let sqlite = EvalHarnessSupport.resolveExecutable("sqlite3") ?? URL(fileURLWithPath: "/usr/bin/sqlite3")

        var exec: [Bool] = [], exact: [Bool] = []
        var rowOutputs: [[String: Any]] = []
        for (idx, line) in raw.split(separator: "\n").enumerated() {
            guard let d = line.data(using: .utf8),
                  let o = try? JSONSerialization.jsonObject(with: d) as? [String: Any],
                  let rawPred = o["predicted_sql"] as? String,
                  let gold = o["gold_sql"] as? String,
                  let db = o["db"] as? String else { continue }
            let pred = SqlEval.extractFirstSelect(rawPred) ?? rawPred
            let dbPath = dbDir.map { ($0 as NSString).appendingPathComponent(db) } ?? db
            let pr = runSqlite(sqlite, db: dbPath, sql: pred)
            let gr = runSqlite(sqlite, db: dbPath, sql: gold)
            let execMatch = pr.rows != nil && gr.rows != nil && SqlEval.executionMatch(pr.rows!, gr.rows!)
            let exactMatch = SqlEval.exactMatch(pred, gold)
            exec.append(execMatch)
            exact.append(exactMatch)

            var row: [String: Any] = [
                "index": idx,
                "db": db,
                "predicted_sql": rawPred,
                "scored_sql": pred,
                "gold_sql": gold,
                "exec_match": execMatch,
                "exact_match": exactMatch,
            ]
            if let question = o["question"] as? String {
                row["question"] = question
            }
            if let predictedError = pr.error {
                row["predicted_error"] = predictedError
            }
            if let goldError = gr.error {
                row["gold_error"] = goldError
            }
            if !execMatch {
                row["predicted_rows"] = pr.rows ?? []
                row["gold_rows"] = gr.rows ?? []
            }
            rowOutputs.append(row)
        }
        guard !exec.isEmpty else { fputs("no valid SQL rows\n", stderr); exit(1) }
        let r = SqlEval.score(execMatches: exec, exactMatches: exact)
        print(String(format: "sql: execution_accuracy=%.3f exact_match=%.3f (n=%d)",
                     r.execAccuracy, r.exactMatch, r.n))
        if let outPath = outPath {
            let lines = rowOutputs.compactMap { try? String(data: JSONSerialization.data(withJSONObject: $0, options: [.sortedKeys]), encoding: .utf8) }
            try? (lines.joined(separator: "\n") + "\n").write(toFile: outPath, atomically: true, encoding: .utf8)
        }
    }

    /// Run one query; return rows (cells split on 0x1f) or a SQLite error.
    static func runSqlite(_ sqlite: URL, db: String, sql: String) -> SqliteResult {
        let p = Process()
        p.executableURL = sqlite
        p.arguments = ["-batch", "-noheader", "-separator", "\u{1f}", db, sql]
        let out = Pipe(); let err = Pipe()
        p.standardOutput = out; p.standardError = err
        do { try p.run() } catch { return SqliteResult(rows: nil, error: "\(error)") }
        p.waitUntilExit()
        let errData = err.fileHandleForReading.readDataToEndOfFile()
        let errText = String(data: errData, encoding: .utf8)?
            .trimmingCharacters(in: .whitespacesAndNewlines)
        if p.terminationStatus != 0 {
            return SqliteResult(rows: nil, error: errText?.isEmpty == false ? errText : "sqlite exited \(p.terminationStatus)")
        }
        let data = out.fileHandleForReading.readDataToEndOfFile()
        let text = String(data: data, encoding: .utf8) ?? ""
        let rows = text.split(separator: "\n", omittingEmptySubsequences: true).map {
            $0.components(separatedBy: "\u{1f}")
        }
        return SqliteResult(rows: rows, error: nil)
    }

    struct SqliteResult {
        let rows: [[String]]?
        let error: String?
    }

    private static func exitUsage(_ code: Int32 = 2) -> Never {
        print("""
        usage: tinygpt eval-sql <preds.jsonl> [--db-dir <dir>] [--out rows.jsonl]

        Execution-accuracy eval for text-to-SQL (B1). Rows:
          {predicted_sql, gold_sql, db}   (db relative to --db-dir if given)
        Runs both queries via sqlite3, reports execution accuracy (result-set
        match, order-insensitive) + normalized exact-match. With --out, writes
        row-level traces with SQL text, pass/fail flags, sqlite errors, and
        mismatched result rows. Generation is the GPU step; this scores its
        output.
        """)
        exit(code)
    }
}
