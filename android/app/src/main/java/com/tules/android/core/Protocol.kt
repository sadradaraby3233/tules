package com.tules.android.core

import org.json.JSONArray
import org.json.JSONObject
import org.json.JSONTokener

object Protocol {
    /** Extract the first envelope, respecting endedit inside JSON strings. */
    fun extract(input: String): String {
        val start = Regex("(?i)edit:\\s*").find(input) ?: error("No edit: ... endedit block found")
        var quoted = false
        var escaped = false
        var end = start.range.last + 1
        while (end < input.length) {
            val c = input[end]
            when {
                escaped -> escaped = false
                quoted && c == '\\' -> escaped = true
                c == '"' -> quoted = !quoted
                !quoted && input.regionMatches(end, "endedit", 0, 7, ignoreCase = true) -> {
                    var body = input.substring(start.range.last + 1, end).trim()
                    body = body.replace(Regex("^```(?:json)?\\s*", RegexOption.IGNORE_CASE), "")
                    body = body.replace(Regex("\\s*```$"), "").trim()
                    return body
                }
            }
            end++
        }
        error("Missing endedit marker")
    }

    fun decode(input: String): List<JSONObject> {
        require(input.length <= 2_000_000) { "Command block exceeds 2 million characters" }
        val tokener = JSONTokener(extract(input))
        val value = tokener.nextValue()
        require(tokener.nextClean() == '\u0000') { "Unexpected text after JSON" }
        val commands = when (value) {
            is JSONObject -> listOf(value)
            is JSONArray -> (0 until value.length()).map {
                value.opt(it) as? JSONObject ?: error("Every batch item must be an object")
            }
            else -> error("Payload must be a JSON object or array")
        }
        require(commands.isNotEmpty() && commands.size <= 30) { "A batch must contain 1–30 commands" }
        return commands
    }
}
