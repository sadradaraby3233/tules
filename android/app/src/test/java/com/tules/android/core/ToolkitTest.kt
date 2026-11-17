package com.tules.android.core

import org.junit.Assert.*
import org.junit.Test

private class FakeWorkspace : Workspace {
    val files = linkedMapOf("notes.txt" to "one\ntwo\nthree")
    private val backups = mutableMapOf<String, String>()
    override fun listFiles() = files.keys.toList()
    override fun read(path: String) = files[path] ?: error("File not found: $path")
    override fun write(path: String, content: String, createOnly: Boolean) {
        if (createOnly && path in files) error("Already exists")
        files[path]?.let { backups[path] = it }
        files[path] = content
    }
    override fun undo(path: String) { files[path] = backups[path] ?: error("No backup") }
}

class ToolkitTest {
    private val workspace = FakeWorkspace()
    private val toolkit = Toolkit(workspace)
    private fun run(json: String) = toolkit.execute("edit: $json endedit")

    @Test fun envelopeKeepsEndMarkerInsideStrings() {
        assertEquals("{\"action\":\"write\",\"content\":\"endedit\"}",
            Protocol.extract("edit: {\"action\":\"write\",\"content\":\"endedit\"} endedit"))
    }
    @Test fun malformedAndMissingEnvelopeFail() {
        assertTrue(toolkit.execute("hello").startsWith("STATUS: FAILED"))
        assertTrue(run("{bad").startsWith("STATUS: FAILED"))
    }
    @Test fun batchRunsInOrderAndReportsFailures() {
        val reply = run("""[{"action":"read_file","file":"missing"},{"action":"help"}]""")
        assertTrue(reply.contains("SUCCESS: 1 | FAILED: 1"))
    }
    @Test fun exactEditAndUndo() {
        assertTrue(run("""{"action":"replace","file":"notes.txt","old_string":"two","new_string":"changed"}""").startsWith("STATUS: SUCCESS"))
        assertEquals("one\nchanged\nthree", workspace.read("notes.txt"))
        assertTrue(run("""{"action":"undo","file":"notes.txt"}""").startsWith("STATUS: SUCCESS"))
        assertEquals("one\ntwo\nthree", workspace.read("notes.txt"))
    }
    @Test fun ambiguousAndInvalidBooleanNeverEdit() {
        workspace.files["notes.txt"] = "same same"
        assertTrue(run("""{"action":"replace","file":"notes.txt","old_string":"same","new_string":"x"}""").startsWith("STATUS: FAILED"))
        assertTrue(run("""{"action":"replace","file":"notes.txt","old_string":"same","new_string":"x","replace_all":"false"}""").startsWith("STATUS: FAILED"))
        assertEquals("same same", workspace.read("notes.txt"))
    }
    @Test fun overlappingMatchesAreNotGuessed() {
        workspace.files["notes.txt"] = "aaa"
        assertTrue(run("""{"action":"replace","file":"notes.txt","old_string":"aa","new_string":"x","replace_all":true}""").startsWith("STATUS: FAILED"))
        assertEquals("aaa", workspace.read("notes.txt"))
    }
    @Test fun readIncludesContinuation() {
        val result = run("""{"action":"read_file","file":"notes.txt","start_line":1,"end_line":1}""")
        assertTrue(result.contains("truncated: true"))
        assertTrue(result.contains("\"start_line\":2"))
    }
    @Test fun createDoesNotClobberExisting() {
        assertTrue(run("""{"action":"create_file","file":"notes.txt","content":"oops"}""").startsWith("STATUS: FAILED"))
        assertEquals("one\ntwo\nthree", workspace.read("notes.txt"))
    }
    @Test fun unsupportedShellFails() {
        assertTrue(run("""{"action":"bash","command":"echo hi"}""").startsWith("STATUS: FAILED"))
    }
}
