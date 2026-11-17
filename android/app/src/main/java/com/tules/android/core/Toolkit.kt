package com.tules.android.core

import org.json.JSONObject

interface Workspace {
    fun listFiles(): List<String>
    fun read(path: String): String
    /** Existing files must be backed up before writing. */
    fun write(path: String, content: String, createOnly: Boolean)
    fun undo(path: String)
}

/** Small, deliberately explicit Android subset of the desktop command protocol. */
class Toolkit(private val workspace: Workspace) {
    fun execute(input: String): String {
        val commands = try { Protocol.decode(input) } catch (e: Exception) {
            return failed(e.message ?: "Invalid command block")
        }
        val results = commands.map { command ->
            try { executeOne(command) } catch (e: Exception) { failed(e.message ?: "Operation failed") }
        }
        if (results.size == 1) return results[0]
        val successes = results.count { it.startsWith("STATUS: SUCCESS") }
        return "BATCH EXECUTION COMPLETE\nTOTAL: ${results.size} | SUCCESS: $successes | FAILED: ${results.size - successes}\n" +
            results.mapIndexed { i, result -> "\n[COMMAND ${i + 1}/${results.size}]\n$result" }.joinToString("\n")
    }

    private fun executeOne(command: JSONObject): String {
        val action = required(command, "action").lowercase()
        return when (action) {
            "help", "list_actions" -> ok("Android actions", HELP)
            "list_files" -> {
                val pattern = optional(command, "pattern", "")
                val files = workspace.listFiles().filter { it.contains(pattern, ignoreCase = true) }
                ok("Found ${files.size} file(s)", files.joinToString("\n"))
            }
            "read", "read_file", "view" -> {
                val path = file(command)
                val lines = workspace.read(path).split('\n')
                val start = integer(command, if (action == "read") "offset" else "start_line", 1)
                val end = if (command.has("end_line")) integer(command, "end_line", start) else {
                    val limit = integer(command, "limit", 100)
                    require(limit in 1..200) { "limit must be between 1 and 200" }
                    (start.toLong() + limit - 1).coerceAtMost(Int.MAX_VALUE.toLong()).toInt()
                }
                require(start >= 1 && end >= start && end.toLong() - start < 200) { "Line range must be positive and no more than 200 lines" }
                val selected = if (start > lines.size) emptyList() else lines.subList(start - 1, minOf(end, lines.size))
                // Limit total text without silently losing a continuation position.
                val shown = mutableListOf<String>()
                var chars = 0
                for (line in selected) {
                    require(line.length <= 8_000) { "Line is too long to return safely (8,000 character limit)" }
                    if (chars + line.length + 1 > 12_000) break
                    shown.add(line); chars += line.length + 1
                }
                val next = start + shown.size
                val more = next <= lines.size
                val continuation = if (more) "\ntruncated: true\nnext: ${JSONObject().put("action", "read_file").put("file", path).put("start_line", next)}" else "\ntruncated: false"
                ok("Read $path (total lines: ${lines.size})", shown.joinToString("\n") + continuation)
            }
            "search" -> {
                val query = required(command, "search")
                require(query.isNotEmpty()) { "search must not be empty" }
                val hits = mutableListOf<String>()
                var skipped = 0
                for (path in workspace.listFiles()) {
                    val content = try { workspace.read(path) } catch (_: Exception) { skipped++; continue }
                    content.lineSequence().forEachIndexed { index, line ->
                        if (line.contains(query, ignoreCase = true) && hits.size < 100) {
                            hits.add("$path:${index + 1}:${line.take(300)}")
                        }
                    }
                }
                ok("Search results (up to 100; $skipped file(s) unreadable or non-text)", hits.joinToString("\n"))
            }
            "replace" -> {
                val path = file(command)
                val old = first(command, "old_string", "old_str", "search")
                val new = first(command, "new_string", "new_str", "replace_with")
                require(old.isNotEmpty()) { "old_string must not be empty" }
                val original = workspace.read(path)
                var count = 0
                var position = original.indexOf(old)
                var previous = -old.length
                var overlaps = false
                while (position >= 0) {
                    if (position < previous + old.length) overlaps = true
                    previous = position
                    count++
                    position = original.indexOf(old, position + 1)
                }
                require(!overlaps) { "Overlapping matches are ambiguous; provide a longer old_string" }
                require(count > 0) { "No exact match found" }
                val all = boolean(command, "replace_all", false)
                require(count == 1 || all) { "Ambiguous: $count matches; provide a unique old_string or replace_all: true" }
                workspace.write(path, if (all) original.replace(old, new) else original.replaceFirst(old, new), false)
                ok("Replaced $count occurrence(s) in $path", "A backup was saved before writing.")
            }
            "write", "create_file" -> {
                val path = file(command)
                workspace.write(path, required(command, "content"), action == "create_file")
                ok("Wrote $path", "Existing files are backed up before writing.")
            }
            "undo" -> { val path = file(command); workspace.undo(path); ok("Restored $path", "") }
            else -> error("Unknown or unsupported Android action: $action. Use help for available actions.")
        }
    }

    private fun required(obj: JSONObject, key: String): String = obj.opt(key) as? String
        ?: error("'$key' must be a string")
    private fun first(obj: JSONObject, vararg keys: String): String {
        for (key in keys) if (obj.has(key)) return required(obj, key)
        error("Missing one of: ${keys.joinToString()}")
    }
    private fun file(obj: JSONObject) = first(obj, "file", "file_path")
    private fun optional(obj: JSONObject, key: String, default: String) = if (obj.has(key)) required(obj, key) else default
    private fun integer(obj: JSONObject, key: String, default: Int): Int {
        if (!obj.has(key)) return default
        val n = obj.opt(key)
        require(n is Int || n is Long) { "'$key' must be an integer" }
        val value = (n as Number).toLong()
        require(value in Int.MIN_VALUE.toLong()..Int.MAX_VALUE.toLong()) { "'$key' is out of range" }
        return value.toInt()
    }
    private fun boolean(obj: JSONObject, key: String, default: Boolean): Boolean {
        if (!obj.has(key)) return default
        return obj.opt(key) as? Boolean ?: error("'$key' must be true or false")
    }
    private fun ok(message: String, content: String) = "STATUS: SUCCESS\nMESSAGE: $message\nDETAILS:\n$content"
    private fun failed(message: String) = "STATUS: FAILED\nMESSAGE: $message"

    companion object {
        val HELP = """Android subset (valid JSON only; file paths are relative to the selected folder):
{"action":"list_files","pattern":"optional name fragment"}
{"action":"read_file","file":"src/main.py","start_line":1,"end_line":100}
{"action":"search","search":"text"}
{"action":"replace","file":"a.txt","old_string":"old","new_string":"new"}
{"action":"write","file":"a.txt","content":"full contents"}
{"action":"create_file","file":"new.txt","content":"contents"}
{"action":"undo","file":"a.txt"}
Only exact replacement is supported; ambiguous matches fail unless replace_all is true. No shell, browser automation, web, Python syntax validation, or desktop-only actions. Commands in a batch run sequentially, not transactionally. Inspect and verify edits."""
        val PROMPT = """You are using TULES Android. I copy your response, open TULES, review and run it, then paste back its result. Send ONE edit: ... endedit block containing a valid JSON object or array. Start with {"action":"help"} to discover the Android subset. Paths are relative to the selected folder. Read before editing, use exact matches, check STATUS, and verify changes. No shell is available. Batches are not transactional.

edit:
{"action":"help"}
endedit"""
    }
}
