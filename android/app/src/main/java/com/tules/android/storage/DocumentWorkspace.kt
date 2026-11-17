package com.tules.android.storage

import android.content.Context
import android.net.Uri
import android.util.AtomicFile
import androidx.documentfile.provider.DocumentFile
import com.tules.android.core.Workspace
import org.json.JSONTokener
import java.nio.ByteBuffer
import java.nio.charset.CodingErrorAction
import java.security.MessageDigest

/** Storage Access Framework access, scoped to the user's persisted tree grant. */
class DocumentWorkspace(private val context: Context, private val tree: Uri) : Workspace {
    private val resolver = context.contentResolver
    private val root: DocumentFile get() = DocumentFile.fromTreeUri(context, tree)
        ?: error("Workspace access is unavailable; select the folder again")

    private fun parts(path: String): List<String> {
        require(path.isNotBlank() && !path.startsWith('/') && !path.contains('\\')) { "Use a relative path with / separators" }
        val segments = path.split('/')
        require(segments.all { it.isNotBlank() && it != "." && it != ".." }) { "Invalid path" }
        return segments
    }

    private fun child(parent: DocumentFile, name: String): DocumentFile? {
        val matches = parent.listFiles().filter { it.name == name }
        require(matches.size <= 1) { "Provider returned duplicate names: $name" }
        return matches.firstOrNull()
    }

    private fun parent(path: String): Pair<DocumentFile, String> {
        val segments = parts(path)
        var dir = root
        for (segment in segments.dropLast(1)) {
            dir = child(dir, segment) ?: error("Directory not found: $segment")
            require(dir.isDirectory) { "Not a directory: $segment" }
        }
        return dir to segments.last()
    }

    private fun document(path: String): DocumentFile {
        val (dir, name) = parent(path)
        val file = child(dir, name) ?: error("File not found: $path")
        require(file.isFile) { "Not a file: $path" }
        return file
    }

    override fun listFiles(): List<String> {
        val files = mutableListOf<String>()
        var visited = 0
        fun visit(dir: DocumentFile, prefix: String, depth: Int) {
            require(depth <= 20) { "Directory depth exceeds 20; select a smaller workspace" }
            for (item in dir.listFiles().sortedBy { it.name }) {
                visited++
                require(visited <= 2_000) { "Workspace exceeds 2,000 entries; select a smaller folder" }
                val name = item.name ?: continue
                if (name.startsWith('.') || name in setOf("node_modules", "build", "dist", "__pycache__")) continue
                val path = if (prefix.isEmpty()) name else "$prefix/$name"
                if (item.isDirectory) visit(item, path, depth + 1)
                else if (item.isFile) {
                    files.add(path)
                    require(files.size <= 500) { "Workspace exceeds 500 files; select a smaller folder" }
                }
            }
        }
        visit(root, "", 0)
        return files
    }

    private fun bytes(file: DocumentFile): ByteArray {
        val stream = resolver.openInputStream(file.uri) ?: error("Cannot open file for reading")
        return stream.use {
            val output = java.io.ByteArrayOutputStream()
            val buffer = ByteArray(8192)
            while (true) {
                val count = it.read(buffer)
                if (count == -1) break
                require(output.size() + count <= MAX_BYTES) { "File exceeds 1 MiB limit" }
                output.write(buffer, 0, count)
            }
            output.toByteArray()
        }
    }

    override fun read(path: String): String {
        val data = bytes(document(path))
        require(data.none { it == 0.toByte() }) { "Binary files are not supported" }
        return Charsets.UTF_8.newDecoder().onMalformedInput(CodingErrorAction.REPORT)
            .onUnmappableCharacter(CodingErrorAction.REPORT).decode(ByteBuffer.wrap(data)).toString()
    }

    private fun backup(path: String): AtomicFile {
        val hash = MessageDigest.getInstance("SHA-256")
            .digest((tree.toString() + "\u0000" + path).toByteArray(Charsets.UTF_8))
            .joinToString("") { "%02x".format(it.toInt() and 0xff) }
        val dir = context.filesDir.resolve("backups").apply { mkdirs() }
        return AtomicFile(dir.resolve(hash))
    }

    private fun saveBackup(path: String, data: ByteArray) {
        val backup = backup(path)
        val stream = backup.startWrite()
        try { stream.write(data); backup.finishWrite(stream) } catch (e: Exception) {
            backup.failWrite(stream); throw e
        }
    }

    private fun validate(path: String, content: String): ByteArray {
        require('\u0000' !in content) { "Binary content is not supported" }
        val data = content.toByteArray(Charsets.UTF_8)
        require(data.size <= MAX_BYTES) { "File exceeds 1 MiB limit" }
        if (path.endsWith(".json", ignoreCase = true)) {
            val tokener = JSONTokener(content)
            tokener.nextValue()
            require(tokener.nextClean() == '\u0000') { "Invalid JSON: trailing text" }
        }
        return data
    }

    private fun writeBytes(file: DocumentFile, data: ByteArray) {
        val stream = resolver.openOutputStream(file.uri, "wt") ?: error("Cannot open file for writing")
        stream.use { it.write(data); it.flush() }
        require(bytes(file).contentEquals(data)) { "Provider did not preserve the written bytes; restore the backup" }
    }

    override fun write(path: String, content: String, createOnly: Boolean) {
        val data = validate(path, content)
        val (dir, name) = parent(path)
        val existing = child(dir, name)
        if (existing != null) {
            require(!createOnly) { "File already exists: $path" }
            require(existing.isFile) { "Not a file: $path" }
            saveBackup(path, bytes(existing))
            try { writeBytes(existing, data) } catch (e: Exception) {
                error("Write failed; file may be partially changed. Use undo. ${e.message}")
            }
        } else {
            val created = dir.createFile("application/octet-stream", name) ?: error("Provider could not create file")
            // A prior file may have been deleted outside TULES. Its backup must not
            // become the undo target for this newly created file.
            backup(path).delete()
            try { writeBytes(created, data) } catch (e: Exception) {
                val removed = created.delete()
                error("Create failed${if (removed) "" else "; a partial file may remain"}. ${e.message}")
            }
        }
    }

    override fun undo(path: String) {
        val file = document(path)
        val data = try { backup(path).readFully() } catch (_: Exception) { error("No readable backup for $path") }
        try { writeBytes(file, data) } catch (e: Exception) {
            error("Restore failed; file may be partially changed. The backup is retained. ${e.message}")
        }
    }

    companion object { private const val MAX_BYTES = 1024 * 1024 }
}
