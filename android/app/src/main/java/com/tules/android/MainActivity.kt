package com.tules.android

import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.content.Intent
import android.net.Uri
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.lifecycle.lifecycleScope
import com.tules.android.core.Toolkit
import com.tules.android.storage.DocumentWorkspace
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

class MainActivity : ComponentActivity() {
    private val preferences by lazy { getSharedPreferences("workspace", Context.MODE_PRIVATE) }
    private val clipboard by lazy { getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent { MaterialTheme(colorScheme = lightColorScheme()) { Screen() } }
    }

    @Composable
    private fun Screen() {
        var workspace by remember { mutableStateOf(preferences.getString("tree", null)) }
        var input by rememberSaveable { mutableStateOf("") }
        var result by rememberSaveable { mutableStateOf("") }
        var notice by rememberSaveable { mutableStateOf("") }
        var busy by remember { mutableStateOf(false) }
        val folderPicker = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocumentTree()) { uri ->
            if (uri != null) {
                try {
                    contentResolver.takePersistableUriPermission(uri, Intent.FLAG_GRANT_READ_URI_PERMISSION or Intent.FLAG_GRANT_WRITE_URI_PERMISSION)
                    preferences.edit().putString("tree", uri.toString()).apply()
                    workspace = uri.toString()
                    notice = "Workspace access saved. Review commands before running them."
                } catch (e: SecurityException) {
                    notice = "Could not save read/write access to this folder. Choose another folder."
                }
            }
        }
        Surface(modifier = Modifier.fillMaxSize()) {
            Column(
                modifier = Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(20.dp),
                verticalArrangement = Arrangement.spacedBy(12.dp)
            ) {
                Text("TULES", style = MaterialTheme.typography.headlineMedium, fontWeight = FontWeight.Bold)
                Text("Your files. Your AI chat. You stay in control.", style = MaterialTheme.typography.bodyLarge)
                Card(colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.secondaryContainer)) {
                    Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                        Text("1  Choose a workspace", fontWeight = FontWeight.SemiBold)
                        Text(if (workspace == null) "No folder selected" else "Folder: ${workspace?.let { Uri.parse(it).lastPathSegment } ?: "selected"}", style = MaterialTheme.typography.bodyMedium)
                        OutlinedButton(onClick = { folderPicker.launch(null) }, enabled = !busy) { Text("Choose folder") }
                    }
                }
                Text("2  Give your chat the Android prompt", fontWeight = FontWeight.SemiBold)
                OutlinedButton(onClick = {
                    clipboard.setPrimaryClip(ClipData.newPlainText("TULES Android prompt", Toolkit.PROMPT))
                    notice = "Prompt copied. Paste it into your chat."
                }) { Text("Copy setup prompt") }
                Text("3  Copy the chat’s edit block, then return here", fontWeight = FontWeight.SemiBold)
                Text("Tip: add TULES to Quick Settings for a shortcut. Android prevents ordinary apps from monitoring the clipboard in the background.", style = MaterialTheme.typography.bodySmall)
                OutlinedButton(onClick = {
                    try {
                        val clip = clipboard.primaryClip
                        val value = if (clip != null && clip.itemCount > 0) clip.getItemAt(0).text?.toString() else null
                        if (value == null) notice = "No plain text on the clipboard. Copy a chat response first."
                        else if (value.length > 2_000_000) notice = "Clipboard text is too large (2 million character limit)."
                        else { input = value; notice = "Clipboard loaded. Review the command below before running." }
                    } catch (e: Exception) { notice = "Could not read clipboard: ${e.message}" }
                }, enabled = !busy) { Text("Load clipboard") }
                OutlinedTextField(
                    value = input, onValueChange = { input = it }, modifier = Modifier.fillMaxWidth().heightIn(min = 160.dp),
                    label = { Text("Command to review") }, placeholder = { Text("edit: ... endedit") }, enabled = !busy
                )
                Button(onClick = {
                    val selected = workspace
                    if (selected == null) { notice = "Choose a workspace first."; return@Button }
                    val command = input
                    busy = true
                    notice = "Running…"
                    lifecycleScope.launch {
                        val response = withContext(Dispatchers.IO) {
                            try { Toolkit(DocumentWorkspace(this@MainActivity, Uri.parse(selected))).execute(command) }
                            catch (e: Exception) { "STATUS: FAILED\nMESSAGE: ${e.message ?: "Workspace unavailable"}" }
                        }
                        result = response
                        busy = false
                        notice = "Finished. Review and copy the result back to your chat."
                    }
                }, enabled = !busy && input.isNotBlank() && workspace != null, modifier = Modifier.fillMaxWidth()) {
                    Text(if (busy) "Running…" else "Run reviewed command")
                }
                if (notice.isNotBlank()) Text(notice, color = MaterialTheme.colorScheme.primary, style = MaterialTheme.typography.bodyMedium)
                if (result.isNotEmpty()) {
                    HorizontalDivider()
                    Text("Result", style = MaterialTheme.typography.titleLarge)
                    SelectionContainerText(result)
                    Button(onClick = {
                        clipboard.setPrimaryClip(ClipData.newPlainText("TULES result", result))
                        notice = "Result copied. Return to your chat and paste it."
                    }, enabled = !busy) { Text("Copy result") }
                }
                Spacer(Modifier.height(16.dp))
            }
        }
    }
}

@Composable
private fun SelectionContainerText(text: String) {
    androidx.compose.foundation.text.selection.SelectionContainer {
        Text(text, style = MaterialTheme.typography.bodySmall)
    }
}
