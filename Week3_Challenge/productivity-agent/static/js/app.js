// ============================================================
// ELEMENT REFERENCES
// ============================================================

var chatForm = document.getElementById("chatForm");
var chatInput = document.getElementById("chatInput");
var sendBtn = document.getElementById("sendBtn");
var chatMessages = document.getElementById("chatMessages");

var statusBar = document.getElementById("statusBar");
var statusText = document.getElementById("statusText");
var execTimeline = document.getElementById("execTimeline");

var approvalCard = document.getElementById("approvalCard");
var approvalTool = document.getElementById("approvalTool");
var approvalTitle = document.getElementById("approvalTitle");
var approvalDesc = document.getElementById("approvalDesc");
var approvalArgs = document.getElementById("approvalArgs");
var editBtn = document.getElementById("editBtn");
var approveBtn = document.getElementById("approveBtn");
var rejectBtn = document.getElementById("rejectBtn");

var errorBanner = document.getElementById("errorBanner");
var historyEmpty = document.getElementById("historyEmpty");
var logsTable = document.getElementById("logsTable");
var logsTableBody = document.getElementById("logsTableBody");
var logsCount = document.getElementById("logsCount");
var tasksEmpty = document.getElementById("tasksEmpty");
var newTaskBtn = document.getElementById("newTaskBtn");
var taskModal = document.getElementById("taskModal");
var taskModalTitle = document.getElementById("taskModalTitle");
var taskModalCloseBtn = document.getElementById("taskModalCloseBtn");
var taskForm = document.getElementById("taskForm");
var taskFieldTitle = document.getElementById("taskFieldTitle");
var taskFieldDescription = document.getElementById("taskFieldDescription");
var taskFieldPriority = document.getElementById("taskFieldPriority");
var taskFieldStatus = document.getElementById("taskFieldStatus");
var taskFieldDueDate = document.getElementById("taskFieldDueDate");
var taskFieldSource = document.getElementById("taskFieldSource");
var taskFieldTags = document.getElementById("taskFieldTags");
var taskFieldNotes = document.getElementById("taskFieldNotes");
var taskModalMeta = document.getElementById("taskModalMeta");
var taskDeleteBtn = document.getElementById("taskDeleteBtn");

var notesList = document.getElementById("notesList");
var notesEmpty = document.getElementById("notesEmpty");
var notesDetail = document.getElementById("notesDetail");
var newNoteBtn = document.getElementById("newNoteBtn");
var notesSearchInput = document.getElementById("notesSearchInput");

var settingsModal = document.getElementById("settingsModal");
var settingsCloseBtn = document.getElementById("settingsCloseBtn");
var settingsConfigRows = document.getElementById("settingsConfigRows");
var themeToggle = document.getElementById("themeToggle");
var exportChatBtn = document.getElementById("exportChatBtn");


// ============================================================
// STATUS INDICATOR
// Color is chosen by CATEGORY, not by which step number this is:
//   working (blue)  -> thinking / selecting tool / executing
//   approval (amber) -> waiting for the user
//   done (green)     -> finished successfully
//   error (red)      -> something went wrong
// ============================================================

function showStatus(kind, text) {
  statusBar.hidden = false;
  statusBar.setAttribute("data-kind", kind);
  statusText.textContent = text;
}

function hideStatus() {
  statusBar.hidden = true;
}


// ============================================================
// CHAT MESSAGES
// ============================================================

function escapeHtml(text) {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

// Minimal markdown-to-HTML for the agent's replies only. Everything from
// the model is escaped first (escapeHtml, below) so no raw tag or on*
// attribute it emits can ever reach the DOM as real markup — only the
// handful of tags *this* function builds (strong/em/code/pre/ul/ol/li/
// h1-3/br) ever get inserted. No CDN/markdown library is pulled in since
// this app has no existing JS dependency loading pattern to match.
function formatAgentMessage(rawText) {
  var codeBlocks = [];
  // "@@CB0@@" etc. stand in for each code block while the rest of the
  // text goes through escaping/formatting below, then get swapped back
  // for real <pre><code> blocks at the very end.
  var withPlaceholders = rawText.replace(/```([\s\S]*?)```/g, function (match, code) {
    codeBlocks.push(code.replace(/^\n/, "").replace(/\n$/, ""));
    return "@@CB" + (codeBlocks.length - 1) + "@@";
  });

  var html = escapeHtml(withPlaceholders);

  // Headings
  html = html
    .replace(/^### (.+)$/gm, "<h3>$1</h3>")
    .replace(/^## (.+)$/gm, "<h2>$1</h2>")
    .replace(/^# (.+)$/gm, "<h1>$1</h1>");

  // Bullet and numbered lists — group consecutive matching lines into one
  // <ul>/<ol> rather than wrapping each line individually.
  html = html.replace(/(^(?:[-*] .+\n?)+)/gm, function (block) {
    var items = block.trim().split("\n").map(function (line) {
      return "<li>" + line.replace(/^[-*]\s+/, "") + "</li>";
    }).join("");
    return "<ul>" + items + "</ul>\n";
  });
  html = html.replace(/(^(?:\d+\. .+\n?)+)/gm, function (block) {
    var items = block.trim().split("\n").map(function (line) {
      return "<li>" + line.replace(/^\d+\.\s+/, "") + "</li>";
    }).join("");
    return "<ol>" + items + "</ol>\n";
  });

  // Inline code, bold, italic
  html = html
    .replace(/`([^`\n]+)`/g, "<code>$1</code>")
    .replace(/\*\*([^*\n]+)\*\*/g, "<strong>$1</strong>")
    .replace(/\*([^*\n]+)\*/g, "<em>$1</em>");

  // Remaining line breaks -> <br>, except right after a block-level tag
  html = html.replace(/\n/g, "<br>").replace(/(<\/(?:ul|ol|h1|h2|h3)>)<br>/g, "$1");

  // Restore fenced code blocks last, escaping their content on the way in
  // (it was pulled out above, before the general escapeHtml call).
  html = html.replace(/@@CB(\d+)@@/g, function (match, index) {
    return "<pre><code>" + escapeHtml(codeBlocks[Number(index)]) + "</code></pre>";
  });

  return html;
}

function addMessage(role, text) {
  var emptyState = document.getElementById("chatEmpty");
  if (emptyState) {
    emptyState.hidden = true;
  }

  var bubble = document.createElement("div");
  bubble.className = "msg " + (role === "user" ? "msg--user" : "msg--agent");
  // Raw text is kept on the element (used by chat export) since innerHTML
  // for agent messages no longer round-trips back to the original text.
  bubble.dataset.raw = text;
  if (role === "user") {
    bubble.textContent = text;
  } else {
    bubble.innerHTML = formatAgentMessage(text);
  }
  chatMessages.appendChild(bubble);
  chatMessages.scrollTop = chatMessages.scrollHeight;
}


// ============================================================
// ERROR BANNER (Requirement 8: clear, understandable errors)
// ============================================================

function showError(message) {
  errorBanner.hidden = false;
  errorBanner.textContent = message;
}

function hideError() {
  errorBanner.hidden = true;
}


// ============================================================
// EXECUTION HISTORY
// ============================================================

var allLoadedLogs = [];
var currentLogsFilter = "all";

var STATUS_BADGE_LABELS = {
  answered: "Success",
  error: "Failed",
  awaiting_approval: "Awaiting approval",
};

function renderExecutionLogs(logs) {
  allLoadedLogs = logs;
  logsCount.textContent = logs.length + (logs.length === 1 ? " execution" : " executions");
  applyLogsFilter();
}

function applyLogsFilter() {
  var filtered = currentLogsFilter === "all"
    ? allLoadedLogs
    : allLoadedLogs.filter(function (log) { return log.final_outcome === currentLogsFilter; });

  logsTableBody.innerHTML = "";

  if (filtered.length === 0) {
    historyEmpty.hidden = false;
    logsTable.hidden = true;
    return;
  }

  historyEmpty.hidden = true;
  logsTable.hidden = false;

  filtered.forEach(function (log) {
    var row = document.createElement("tr");

    var timeCell = document.createElement("td");
    timeCell.className = "logs-table__time";
    timeCell.textContent = log.start_time.split("T")[1].split(".")[0];
    row.appendChild(timeCell);

    var requestCell = document.createElement("td");
    requestCell.className = "logs-table__request";
    requestCell.textContent = log.user_request;
    row.appendChild(requestCell);

    var toolsCell = document.createElement("td");
    toolsCell.className = "logs-table__tools";
    toolsCell.textContent = log.tools_called.length > 0 ? log.tools_called.join(", ") : "\u2014";
    row.appendChild(toolsCell);

    var approvalCell = document.createElement("td");
    approvalCell.textContent = log.approval_status.replace(/_/g, " ");
    row.appendChild(approvalCell);

    var durationCell = document.createElement("td");
    durationCell.textContent = log.duration_seconds + "s";
    row.appendChild(durationCell);

    var statusCell = document.createElement("td");
    var badge = document.createElement("span");
    badge.className = "logs-badge logs-badge--" + log.final_outcome;
    badge.textContent = STATUS_BADGE_LABELS[log.final_outcome] || log.final_outcome;
    badge.title = log.final_outcome === "error" ? log.error : "";
    statusCell.appendChild(badge);
    row.appendChild(statusCell);

    logsTableBody.appendChild(row);
  });
}

document.querySelectorAll(".logs-filter-tab").forEach(function (tab) {
  tab.addEventListener("click", function () {
    currentLogsFilter = tab.getAttribute("data-filter");
    document.querySelectorAll(".logs-filter-tab").forEach(function (t) { t.classList.remove("active"); });
    tab.classList.add("active");
    applyLogsFilter();
  });
});

function loadExecutionLogs() {
  fetch("/logs")
    .then(function (response) { return response.json(); })
    .then(function (data) { renderExecutionLogs(data.logs); })
    .catch(function (error) {
      console.error("Failed to load execution logs:", error);
    });
}


// ============================================================
// TASKS BOARD \u2014 columns are Status; cards show Priority, Due
// date, Tags, and Source. Opening a card lets every field be
// edited (or the task deleted) via the Task modal.
// ============================================================

var TASK_STATUSES = ["Pending", "In Progress", "Blocked", "Completed", "Cancelled"];
var STATUS_SLUGS = {
  "Pending": "pending",
  "In Progress": "in_progress",
  "Blocked": "blocked",
  "Completed": "completed",
  "Cancelled": "cancelled",
};
var PRIORITY_SLUGS = { "Low": "low", "Medium": "medium", "High": "high", "Critical": "critical" };

var editingTaskId = null; // null while the Task modal is in "create" mode

function formatDateTime(isoString) {
  var date = new Date(isoString);
  return date.toLocaleDateString() + " " + date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

function parseTags(value) {
  return value.split(",").map(function (tag) { return tag.trim(); }).filter(Boolean);
}

function renderTasksBoard(tasks) {
  tasksEmpty.hidden = tasks.length > 0;

  TASK_STATUSES.forEach(function (status) {
    var slug = STATUS_SLUGS[status];
    var listEl = document.getElementById("taskCol-" + slug);
    var countEl = document.getElementById("taskCount-" + slug);
    var tasksInColumn = tasks.filter(function (task) { return task.status === status; });

    listEl.innerHTML = "";
    countEl.textContent = tasksInColumn.length;
    tasksInColumn.forEach(function (task) { listEl.appendChild(createTaskCard(task)); });
  });
}

function createTaskCard(task) {
  var card = document.createElement("button");
  card.type = "button";
  card.className = "task-card";

  var title = document.createElement("div");
  title.className = "task-card__title";
  title.textContent = task.title;
  card.appendChild(title);

  var priorityBadge = document.createElement("span");
  priorityBadge.className = "priority-badge priority-badge--" + (PRIORITY_SLUGS[task.priority] || "low");
  priorityBadge.textContent = task.priority;
  card.appendChild(priorityBadge);

  var meta = document.createElement("div");
  meta.className = "task-card__meta";

  if (task.due_date) {
    var due = document.createElement("span");
    var isOverdue = new Date(task.due_date) < new Date() && task.status !== "Completed" && task.status !== "Cancelled";
    due.className = "task-card__due" + (isOverdue ? " task-card__due--overdue" : "");
    due.textContent = "Due " + task.due_date.split("T")[0];
    meta.appendChild(due);
  }

  if (task.source) {
    var source = document.createElement("span");
    source.className = "task-card__source";
    source.textContent = task.source;
    meta.appendChild(source);
  }

  if (meta.childNodes.length > 0) {
    card.appendChild(meta);
  }

  if (task.tags && task.tags.length > 0) {
    var tagsWrap = document.createElement("div");
    tagsWrap.className = "task-card__tags";
    task.tags.forEach(function (tag) {
      var chip = document.createElement("span");
      chip.className = "tag-chip";
      chip.textContent = tag;
      tagsWrap.appendChild(chip);
    });
    card.appendChild(tagsWrap);
  }

  card.addEventListener("click", function () { openTaskModal(task); });
  return card;
}

function loadTasksBoard() {
  fetch("/tasks")
    .then(function (response) { return response.json(); })
    .then(function (data) { renderTasksBoard(data.tasks); })
    .catch(function (error) {
      console.error("Failed to load tasks:", error);
    });
}

function openTaskModal(task) {
  editingTaskId = task ? task.task_id : null;
  taskModalTitle.textContent = task ? "Edit Task" : "New Task";
  taskDeleteBtn.hidden = !task;

  taskFieldTitle.value = task ? task.title : "";
  taskFieldDescription.value = task ? task.description : "";
  taskFieldPriority.value = task ? task.priority : "Medium";
  taskFieldStatus.value = task ? task.status : "Pending";
  taskFieldDueDate.value = task && task.due_date ? task.due_date.split("T")[0] : "";
  taskFieldSource.value = task ? task.source : "user";
  taskFieldTags.value = task && task.tags ? task.tags.join(", ") : "";
  taskFieldNotes.value = task ? task.notes : "";

  taskModalMeta.textContent = task
    ? "Created " + formatDateTime(task.created_date) + " \u00b7 Updated " + formatDateTime(task.updated_date)
    : "";

  taskModal.hidden = false;
}

function closeTaskModal() {
  taskModal.hidden = true;
}

newTaskBtn.addEventListener("click", function () { openTaskModal(null); });
taskModalCloseBtn.addEventListener("click", closeTaskModal);
taskModal.addEventListener("click", function (event) {
  if (event.target === taskModal) {
    closeTaskModal();
  }
});

taskForm.addEventListener("submit", function (event) {
  event.preventDefault();

  var isCreating = editingTaskId === null;
  var payload = {
    title: taskFieldTitle.value.trim(),
    description: taskFieldDescription.value,
    priority: taskFieldPriority.value,
    due_date: taskFieldDueDate.value || null,
    source: taskFieldSource.value.trim() || "user",
    tags: parseTags(taskFieldTags.value),
    notes: taskFieldNotes.value,
  };
  if (!isCreating) {
    payload.status = taskFieldStatus.value; // status only changes via update, not create
  }

  var url = isCreating ? "/tasks" : "/tasks/" + editingTaskId;
  fetch(url, {
    method: isCreating ? "POST" : "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  })
    .then(function (response) {
      return response.json().then(function (data) { return { ok: response.ok, data: data }; });
    })
    .then(function (result) {
      if (!result.ok) {
        alert(result.data.error || "Couldn't save that task.");
        return;
      }
      closeTaskModal();
      loadTasksBoard();
    })
    .catch(function (error) {
      alert("Couldn't reach the server to save that task.");
      console.error("Task save failed:", error);
    });
});

taskDeleteBtn.addEventListener("click", function () {
  if (!editingTaskId || !confirm("Delete this task? This can't be undone.")) {
    return;
  }

  fetch("/tasks/" + editingTaskId, { method: "DELETE" })
    .then(function (response) { return response.json(); })
    .then(function () {
      closeTaskModal();
      loadTasksBoard();
    })
    .catch(function (error) {
      alert("Couldn't reach the server to delete that task.");
      console.error("Task delete failed:", error);
    });
});


// ============================================================
// NOTES \u2014 search bar + card list on the left, full detail/edit
// panel on the right. Search is keyword-only for now (see
// /notes/search in app.py for why semantic search isn't wired
// up yet).
// ============================================================

var notesSearchDebounceTimer = null;
var selectedNoteId = null;

function renderNotesList(notes) {
  notesList.innerHTML = "";
  notesEmpty.hidden = notes.length > 0;

  notes.forEach(function (note) {
    var card = document.createElement("button");
    card.type = "button";
    card.className = "note-card" + (note.note_id === selectedNoteId ? " note-card--active" : "");

    var title = document.createElement("div");
    title.className = "note-card__title";
    title.textContent = note.title;
    card.appendChild(title);

    var meta = document.createElement("div");
    meta.className = "note-card__meta";
    var categorySpan = document.createElement("span");
    categorySpan.className = "note-card__category";
    categorySpan.textContent = note.category;
    meta.appendChild(categorySpan);
    var updatedSpan = document.createElement("span");
    updatedSpan.textContent = note.updated_date.split("T")[0];
    meta.appendChild(updatedSpan);
    card.appendChild(meta);

    var preview = document.createElement("div");
    preview.className = "note-card__preview";
    preview.textContent = note.content;
    card.appendChild(preview);

    card.addEventListener("click", function () {
      selectedNoteId = note.note_id;
      renderNotesList(notes);
      renderNoteDetail(note);
    });

    notesList.appendChild(card);
  });
}

function buildMetaItem(label, value) {
  var item = document.createElement("div");
  item.className = "notes-detail__meta-item";
  var labelEl = document.createElement("span");
  labelEl.className = "notes-detail__meta-label";
  labelEl.textContent = label;
  var valueEl = document.createElement("span");
  valueEl.className = "notes-detail__meta-value";
  valueEl.textContent = value;
  item.appendChild(labelEl);
  item.appendChild(valueEl);
  return item;
}

function renderNoteDetail(note) {
  notesDetail.innerHTML = "";

  var header = document.createElement("div");
  header.className = "notes-detail__header";

  var title = document.createElement("h2");
  title.className = "notes-detail__title";
  title.textContent = note.title;
  header.appendChild(title);

  var actions = document.createElement("div");
  actions.className = "notes-detail__actions";

  var editButton = document.createElement("button");
  editButton.type = "button";
  editButton.className = "btn btn--ghost";
  editButton.textContent = "Edit";
  editButton.addEventListener("click", function () { renderNoteForm(note); });
  actions.appendChild(editButton);

  var deleteButton = document.createElement("button");
  deleteButton.type = "button";
  deleteButton.className = "btn btn--reject";
  deleteButton.textContent = "Delete";
  deleteButton.addEventListener("click", function () { deleteNote(note.note_id); });
  actions.appendChild(deleteButton);

  header.appendChild(actions);
  notesDetail.appendChild(header);

  var meta = document.createElement("div");
  meta.className = "notes-detail__meta";
  meta.appendChild(buildMetaItem("Category", note.category));
  meta.appendChild(buildMetaItem("Created", formatDateTime(note.created_date)));
  meta.appendChild(buildMetaItem("Updated", formatDateTime(note.updated_date)));

  if (note.tags && note.tags.length > 0) {
    var tagsItem = document.createElement("div");
    tagsItem.className = "notes-detail__meta-item";
    var tagsLabel = document.createElement("span");
    tagsLabel.className = "notes-detail__meta-label";
    tagsLabel.textContent = "Tags";
    tagsItem.appendChild(tagsLabel);
    var tagsWrap = document.createElement("div");
    tagsWrap.className = "notes-detail__tags";
    note.tags.forEach(function (tag) {
      var chip = document.createElement("span");
      chip.className = "tag-chip";
      chip.textContent = tag;
      tagsWrap.appendChild(chip);
    });
    tagsItem.appendChild(tagsWrap);
    meta.appendChild(tagsItem);
  }
  notesDetail.appendChild(meta);

  var content = document.createElement("div");
  content.className = "notes-detail__content";
  content.textContent = note.content;
  notesDetail.appendChild(content);
}

function buildFormField(labelText, type, value) {
  var wrapper = document.createElement("div");
  wrapper.className = "form-field";

  var label = document.createElement("label");
  label.textContent = labelText;
  wrapper.appendChild(label);

  var input = type === "textarea" ? document.createElement("textarea") : document.createElement("input");
  if (type === "textarea") {
    input.rows = 8;
  } else {
    input.type = type;
  }
  input.value = value || "";
  wrapper.appendChild(input);

  return { wrapper: wrapper, input: input };
}

function renderNoteForm(note) {
  notesDetail.innerHTML = "";

  var form = document.createElement("form");
  form.className = "note-form";

  var titleField = buildFormField("Title", "text", note ? note.title : "");
  var categoryField = buildFormField("Category", "text", note ? note.category : "general");
  var tagsField = buildFormField("Tags (comma-separated)", "text", note && note.tags ? note.tags.join(", ") : "");
  var contentField = buildFormField("Content", "textarea", note ? note.content : "");

  form.appendChild(titleField.wrapper);
  form.appendChild(categoryField.wrapper);
  form.appendChild(tagsField.wrapper);
  form.appendChild(contentField.wrapper);

  var actions = document.createElement("div");
  actions.className = "modal-actions";

  var cancelButton = document.createElement("button");
  cancelButton.type = "button";
  cancelButton.className = "btn btn--ghost";
  cancelButton.textContent = "Cancel";
  cancelButton.addEventListener("click", function () {
    note ? renderNoteDetail(note) : showNotesDetailEmpty();
  });
  actions.appendChild(cancelButton);

  var saveButton = document.createElement("button");
  saveButton.type = "submit";
  saveButton.className = "btn btn--approve";
  saveButton.textContent = "Save Note";
  actions.appendChild(saveButton);

  form.appendChild(actions);
  notesDetail.appendChild(form);

  form.addEventListener("submit", function (event) {
    event.preventDefault();
    saveNote(note ? note.note_id : null, {
      title: titleField.input.value.trim(),
      category: categoryField.input.value.trim() || "general",
      tags: parseTags(tagsField.input.value),
      content: contentField.input.value,
    });
  });

  titleField.input.focus();
}

function showNotesDetailEmpty() {
  selectedNoteId = null;
  notesDetail.innerHTML = "";
  var empty = document.createElement("div");
  empty.className = "notes-detail__empty";
  var text = document.createElement("p");
  text.className = "view__empty";
  text.textContent = "Select a note to view it, or create a new one.";
  empty.appendChild(text);
  notesDetail.appendChild(empty);
}

function saveNote(noteId, payload) {
  var isCreating = noteId === null;
  var url = isCreating ? "/notes" : "/notes/" + noteId;

  fetch(url, {
    method: isCreating ? "POST" : "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  })
    .then(function (response) {
      return response.json().then(function (data) { return { ok: response.ok, data: data }; });
    })
    .then(function (result) {
      if (!result.ok) {
        alert(result.data.error || "Couldn't save that note.");
        return;
      }
      selectedNoteId = result.data.note_id;
      loadNotesView(function () { renderNoteDetail(result.data); });
    })
    .catch(function (error) {
      alert("Couldn't reach the server to save that note.");
      console.error("Note save failed:", error);
    });
}

function deleteNote(noteId) {
  if (!confirm("Delete this note? This can't be undone.")) {
    return;
  }

  fetch("/notes/" + noteId, { method: "DELETE" })
    .then(function (response) { return response.json(); })
    .then(function () {
      showNotesDetailEmpty();
      loadNotesView();
    })
    .catch(function (error) {
      alert("Couldn't reach the server to delete that note.");
      console.error("Note delete failed:", error);
    });
}

function loadNotesView(onDone) {
  fetch("/notes")
    .then(function (response) { return response.json(); })
    .then(function (data) {
      renderNotesList(data.notes);
      if (onDone) {
        onDone();
      }
    })
    .catch(function (error) {
      console.error("Failed to load notes:", error);
    });
}

newNoteBtn.addEventListener("click", function () { renderNoteForm(null); });

notesSearchInput.addEventListener("input", function () {
  var query = notesSearchInput.value.trim();
  clearTimeout(notesSearchDebounceTimer);
  notesSearchDebounceTimer = setTimeout(function () {
    fetch("/notes/search?q=" + encodeURIComponent(query))
      .then(function (response) { return response.json(); })
      .then(function (data) { renderNotesList(data.notes); })
      .catch(function (error) {
        console.error("Note search failed:", error);
      });
  }, 250);
});


// ============================================================
// SETTINGS
// ============================================================

function renderSettings(config) {
  settingsConfigRows.innerHTML = "";

  var rows = [
    ["Generation model", config.generation_model],
    ["Max agent steps", config.max_agent_steps],
    ["Max tool retries", config.max_tool_retries],
    ["Tool timeout (seconds)", config.tool_timeout_seconds],
    ["Database", config.database_url],
  ];

  rows.forEach(function (row) {
    var wrapper = document.createElement("div");
    wrapper.className = "settings-row";
    var label = document.createElement("span");
    label.className = "settings-row__label";
    label.textContent = row[0];
    var value = document.createElement("span");
    value.className = "settings-row__value";
    value.textContent = row[1];
    wrapper.appendChild(label);
    wrapper.appendChild(value);
    settingsConfigRows.appendChild(wrapper);
  });
}

function loadSettings() {
  fetch("/settings")
    .then(function (response) { return response.json(); })
    .then(function (data) { renderSettings(data); })
    .catch(function (error) {
      console.error("Failed to load settings:", error);
    });
}


// ============================================================
// APPROVAL CARD (Requirement 7)
// ============================================================

function showApprovalCard(request) {
  approvalTool.textContent = request.tool_name;
  approvalTitle.textContent = request.title;
  approvalDesc.textContent = request.description;

  approvalArgs.innerHTML = "";
  for (var key in request.arguments) {
    var value = request.arguments[key];
    var isEditable = (typeof value === "string" || typeof value === "number");

    var row = document.createElement("div");
    row.className = "approval-card__arg-row";

    var dt = document.createElement("dt");
    dt.textContent = key;
    row.appendChild(dt);

    var dd = document.createElement("dd");
    dd.textContent = value;
    dd.setAttribute("data-key", key);
    dd.setAttribute("data-editable", isEditable ? "true" : "false");
    row.appendChild(dd);

    approvalArgs.appendChild(row);
  }

  approvalCard.classList.remove("approval-card--editing");
  editBtn.disabled = false;
  approvalCard.hidden = false;
}

function hideApprovalCard() {
  approvalCard.hidden = true;
}

// ============================================================
// EDIT — turns each editable argument into an input field so the
// user can change a value before approving (Requirement 7).
// ============================================================

editBtn.addEventListener("click", function () {
  var rows = approvalArgs.querySelectorAll("dd[data-editable='true']");

  rows.forEach(function (dd) {
    var currentValue = dd.textContent;
    var input = document.createElement("input");
    input.type = "text";
    input.value = currentValue;
    input.className = "approval-card__arg-input";
    input.setAttribute("data-key", dd.getAttribute("data-key"));
    dd.replaceWith(input);
  });

  editBtn.disabled = true;
});

function collectEditedArguments() {
  var edited = {};
  approvalArgs.querySelectorAll(".approval-card__arg-input").forEach(function (input) {
    edited[input.getAttribute("data-key")] = input.value;
  });
  return edited;
}

approveBtn.addEventListener("click", function () {
  var editedArguments = collectEditedArguments();
  hideApprovalCard();
  showStatus("working", "Executing the approved action...");

  fetch("/approve", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ edited_arguments: editedArguments }),
  })
    .then(function (response) { return response.json(); })
    .then(handleAgentResponse)
    .catch(function (error) {
      hideStatus();
      showError("Couldn't reach the agent to approve that action.");
      console.error("Approve request failed:", error);
    });
});

rejectBtn.addEventListener("click", function () {
  hideApprovalCard();

  fetch("/reject", { method: "POST" })
    .then(function (response) { return response.json(); })
    .then(handleAgentResponse)
    .catch(function (error) {
      showError("Couldn't reach the agent to reject that action.");
      console.error("Reject request failed:", error);
    });
});


// ============================================================
// SHARED RESPONSE HANDLER
// Used after /chat, /approve, and /reject — all three return the
// same JSON shape (reply / steps / approval_request / error).
// ============================================================

// ============================================================
// STEP-BY-STEP STATUS PLAYBACK
// The backend returns the full sequence of operational stages for
// this run (thinking / selecting_tool / executing / etc.), each with
// a short operational message only — never private reasoning (the
// server-side prompt design guarantees this). This plays that
// sequence back through the status bar so Selecting Tool and
// Executing Tool are actually visible, not just the final outcome.
// ============================================================

var STAGE_TO_STATUS_KIND = {
  thinking: "working",
  selecting_tool: "working",
  executing: "working",
  waiting_approval: "approval",
  done: "working",
  error: "error",
};

function playStepsSequentially(steps, onComplete) {
  var index = 0;

  function showNextStep() {
    if (index >= steps.length) {
      onComplete();
      return;
    }

    var step = steps[index];
    var kind = STAGE_TO_STATUS_KIND[step.stage] || "working";
    showStatus(kind, step.detail);

    index += 1;
    setTimeout(showNextStep, 450);
  }

  showNextStep();
}


function renderExecutionTimeline(steps) {
  if (!steps || steps.length === 0) {
    execTimeline.hidden = true;
    return;
  }

  function hasStage(stage) {
    return steps.some(function (step) { return step.stage === stage; });
  }
  var lastStage = steps[steps.length - 1].stage;

  var checkpoints = [];
  checkpoints.push({ label: "Understanding", state: "done" });
  if (hasStage("selecting_tool")) checkpoints.push({ label: "Tool Selected", state: "done" });
  if (hasStage("executing")) checkpoints.push({ label: "Executing", state: "done" });
  if (hasStage("waiting_approval")) {
    checkpoints.push({ label: "Approval", state: lastStage === "waiting_approval" ? "active" : "done" });
  }
  if (hasStage("error")) {
    checkpoints.push({ label: "Error", state: "error" });
  } else if (hasStage("done")) {
    checkpoints.push({ label: "Final Response", state: "done" });
  }

  execTimeline.innerHTML = "";
  checkpoints.forEach(function (checkpoint, index) {
    if (index > 0) {
      var connector = document.createElement("div");
      connector.className = "exec-connector" + (checkpoint.state !== "pending" ? " exec-connector--done" : "");
      execTimeline.appendChild(connector);
    }

    var stepEl = document.createElement("div");
    stepEl.className = "exec-step exec-step--" + checkpoint.state;

    var dot = document.createElement("span");
    dot.className = "exec-step__dot";
    dot.textContent = checkpoint.state === "done" ? "\u2713" : (checkpoint.state === "error" ? "\u2715" : "");

    var label = document.createElement("span");
    label.className = "exec-step__label";
    label.textContent = checkpoint.label;

    stepEl.appendChild(dot);
    stepEl.appendChild(label);
    execTimeline.appendChild(stepEl);
  });

  execTimeline.hidden = false;
}


function handleAgentResponse(data) {
  sendBtn.disabled = false;

  var steps = data.steps || [];
  renderExecutionTimeline(steps);

  playStepsSequentially(steps, function () {
    if (data.error) {
      showStatus("error", "Handling an error");
      showError(data.error);
      return;
    }

    if (data.approval_request) {
      showStatus("approval", "Waiting for your approval");
      showApprovalCard(data.approval_request);
    } else {
      showStatus("done", "Final response ready");
      addMessage("agent", data.reply);
    }
  });
}


// ============================================================
// SENDING A MESSAGE
// ============================================================

chatForm.addEventListener("submit", function (event) {
  event.preventDefault();
  hideError();

  var message = chatInput.value.trim();
  if (message === "") {
    return;
  }

  addMessage("user", message);
  chatInput.value = "";
  updateComposerState();
  sendBtn.disabled = true;
  showStatus("working", "Thinking...");

  fetch("/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message: message }),
  })
    .then(function (response) {
      return response.json();
    })
    .then(handleAgentResponse)
    .catch(function (error) {
      sendBtn.disabled = false;
      hideStatus();
      showError("Couldn't reach the agent. Please try again.");
      console.error("Chat request failed:", error);
    });
});


// ============================================================
// SIDEBAR NAV — SWITCHING BETWEEN VIEWS
// Each nav button has a data-view attribute matching a view's
// id (e.g. data-view="tasks" -> #tasksView). Clicking one hides
// every other view and shows just that one.
// ============================================================

var navItems = document.querySelectorAll(".nav-item");
var views = document.querySelectorAll(".view");

function showView(viewName) {
  views.forEach(function (view) {
    view.hidden = view.id !== viewName + "View";
  });

  navItems.forEach(function (item) {
    var isActive = item.getAttribute("data-view") === viewName;
    item.classList.toggle("nav-item--active", isActive);
  });

  if (viewName === "history") {
    loadExecutionLogs();
  } else if (viewName === "tasks") {
    loadTasksBoard();
  } else if (viewName === "notes") {
    showNotesDetailEmpty();
    loadNotesView();
  }
}

navItems.forEach(function (item) {
  item.addEventListener("click", function () {
    var viewName = item.getAttribute("data-view");
    if (viewName === "settings") {
      openSettingsModal();
    } else {
      showView(viewName);
    }
  });
});

function openSettingsModal() {
  settingsModal.hidden = false;
  loadSettings();
}

function closeSettingsModal() {
  settingsModal.hidden = true;
}

settingsCloseBtn.addEventListener("click", closeSettingsModal);
settingsModal.addEventListener("click", function (event) {
  if (event.target === settingsModal) {
    closeSettingsModal();
  }
});


// ============================================================
// SPLASH SCREEN
// Shows the logo drawing in, then reveals the app underneath.
// ============================================================

(function () {
  var splashScreen = document.getElementById("splashScreen");
  var appRoot = document.getElementById("appRoot");

  setTimeout(function () {
    splashScreen.classList.add("splash-screen--hidden");
    appRoot.hidden = false;

    setTimeout(function () {
      splashScreen.style.display = "none";
    }, 500); // matches the CSS fade-out duration
  }, 1700); // gives the last logo bar time to finish drawing in first
})();


// ============================================================
// SUGGESTION CHIPS
// Clicking one fills the chat input, ready to send.
// ============================================================

document.querySelectorAll(".suggestion-chip").forEach(function (chip) {
  chip.addEventListener("click", function () {
    chatInput.value = chip.getAttribute("data-fill");
    updateComposerState();
    chatInput.focus();
  });
});


// ============================================================
// COMPOSER — ready state + autogrow textarea
// The send button lights up teal once there's text to send, and
// the textarea grows with its content instead of scrolling.
// Enter submits (matching the old single-line input's behavior);
// Shift+Enter inserts a newline.
// ============================================================

function updateComposerState() {
  var hasText = chatInput.value.trim().length > 0;
  sendBtn.classList.toggle("is-ready", hasText);

  chatInput.style.height = "auto";
  chatInput.style.height = chatInput.scrollHeight + "px";
}

chatInput.addEventListener("input", updateComposerState);

chatInput.addEventListener("keydown", function (event) {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    chatForm.requestSubmit();
  }
});

updateComposerState();


// ============================================================
// SEARCH — Cmd/Ctrl+K focuses the top bar search input
// ============================================================

var searchInput = document.getElementById("searchInput");

document.addEventListener("keydown", function (event) {
  if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
    event.preventDefault();
    if (searchInput) {
      searchInput.focus();
    }
  }
});


// ============================================================
// TIME-BASED GREETING
// ============================================================

(function () {
  var greetingElement = document.getElementById("chatGreeting");
  if (greetingElement) {
    var hour = new Date().getHours();
    var greeting = hour < 12 ? "Good morning" : hour < 18 ? "Good afternoon" : "Good evening";
    greetingElement.textContent = greeting;
  }
})();


// ============================================================
// THEME TOGGLE
// ============================================================

function setTheme(themeName) {
  document.documentElement.setAttribute("data-theme", themeName);
  localStorage.setItem("trace-theme", themeName);

  themeToggle.querySelectorAll("button").forEach(function (button) {
    button.classList.toggle("active", button.getAttribute("data-theme-choice") === themeName);
  });
}

themeToggle.querySelectorAll("button").forEach(function (button) {
  button.addEventListener("click", function () {
    setTheme(button.getAttribute("data-theme-choice"));
  });
});

// Reflect whichever theme is already active when the modal first opens.
setTheme(document.documentElement.getAttribute("data-theme") || "light");


// ============================================================
// EXPORT CHAT AS PDF
// ============================================================

exportChatBtn.addEventListener("click", function () {
  var messages = [];
  document.querySelectorAll("#chatMessages .msg").forEach(function (bubble) {
    messages.push({
      role: bubble.classList.contains("msg--user") ? "user" : "agent",
      content: bubble.dataset.raw !== undefined ? bubble.dataset.raw : bubble.textContent,
    });
  });

  if (messages.length === 0) {
    alert("There's no conversation yet to export.");
    return;
  }

  fetch("/export-chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ messages: messages }),
  })
    .then(function (response) { return response.blob(); })
    .then(function (blob) {
      var url = window.URL.createObjectURL(blob);
      var link = document.createElement("a");
      link.href = url;
      link.download = "trace-chat-export.pdf";
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    })
    .catch(function (error) {
      console.error("Failed to export chat:", error);
      alert("Couldn't export the chat. Please try again.");
    });
});