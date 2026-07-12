/* ============================================================
   ENTERPRISE DOCUMENT INTELLIGENCE — app.js
   ------------------------------------------------------------
   Plain, beginner-friendly JavaScript.
   No classes, no frameworks, no arrow-function-everywhere style.
   Just functions + addEventListener.

   NOTE: This file only handles FRONTEND behavior.
   Upload progress and AI replies below are PLACEHOLDERS
   (setTimeout / setInterval) until the Flask backend is ready.
   ============================================================ */


/* ============================================================
   SECTION 0: GRAB ELEMENTS WE NEED
   We do this once at the top so every function below can
   just use these variables instead of calling getElementById
   again and again.
   ============================================================ */

// Layout
var sidebar = document.getElementById("sidebar");
var sidebarToggleBtn = document.getElementById("sidebarToggle"); // may not exist yet, we check before using it

// Theme (dark mode)
var themeToggleBtn = document.getElementById("themeToggle");
var htmlElement = document.documentElement; // the <html> tag, where we store data-theme

// Upload / documents
var dropzone = document.getElementById("dropzone");
var fileInput = document.getElementById("fileInput");
var browseBtn = document.getElementById("browseBtn");
var uploadBtn = document.getElementById("uploadBtn");
var docsToggle = document.getElementById("docsToggle");
var docsBody = document.getElementById("docsBody");
var uploadBtnLabel = document.getElementById("uploadBtnLabel");
var attachBtn = document.getElementById("attachBtn");
var dragOverlay = document.getElementById("dragOverlay");

// Chat
var chatForm = document.getElementById("chatForm");
var chatInput = document.getElementById("chatInput");
var sendBtn = document.getElementById("sendBtn");
var chatMessages = document.getElementById("chatMessages");
var chatEmpty = document.getElementById("chatEmpty");
var suggestions = document.getElementById("suggestions");

// Templates (used to create new chat bubbles without writing raw HTML strings)
var tplMessageUser = document.getElementById("tplMessageUser");
var tplMessageAI = document.getElementById("tplMessageAI");
var tplTyping = document.getElementById("tplTyping");
var tplSourceCard = document.getElementById("tplSourceCard");
var tplDocCard = document.getElementById("tplDocCard");

// Document library + statistics
var docGrid = document.getElementById("docGrid");
var docCount = document.getElementById("docCount");

// Confirm modal (used for deleting a document or clearing memory)
var modal = document.getElementById("modal");
var modalTitle = document.getElementById("modalTitle");
var modalMessage = document.getElementById("modalMessage");
var modalCancel = document.getElementById("modalCancel");
var modalConfirm = document.getElementById("modalConfirm");

// Right panel
var clearMemoryBtn = document.getElementById("clearMemoryBtn");
var kbVectors = document.getElementById("kbVectors");
var recentUploadsList = document.getElementById("recentUploads");
var uploadsEmpty = document.getElementById("uploadsEmpty");
var tplUploadItem = document.getElementById("tplUploadItem");
var memorySummary = document.getElementById("memorySummary");
var memoryCount = document.getElementById("memoryCount");
var memoryFill = document.getElementById("memoryFill");
var activityList = document.getElementById("activityList");
var activityEmpty = document.getElementById("activityEmpty");
var tplActivityItem = document.getElementById("tplActivityItem");

// Sidebar navigation + "View all" link (both use data-view)
var navLinksWithView = document.querySelectorAll("[data-view]");

// Settings view
var dashboardView = document.getElementById("dashboardView");
var settingsView = document.getElementById("settingsView");
var exportPdfBtn = document.getElementById("exportPdfBtn");
var settingsEmbeddingModel = document.getElementById("settingsEmbeddingModel");
var settingsLlmProvider = document.getElementById("settingsLlmProvider");
var settingsVectorDb = document.getElementById("settingsVectorDb");

// Conversations view
var conversationsView = document.getElementById("conversationsView");
var conversationList = document.getElementById("conversationList");
var conversationsEmpty = document.getElementById("conversationsEmpty");
var tplConversationItem = document.getElementById("tplConversationItem");
var newChatBtn = document.getElementById("newChatBtn");


/* ============================================================
   SECTION 1: DARK MODE TOGGLE
   Clicking the toggle switches data-theme on <html> between
   "dark" and "light". CSS listens to this attribute.
   ============================================================ */

function toggleDarkMode() {
  var currentTheme = htmlElement.getAttribute("data-theme");

  if (currentTheme === "dark") {
    htmlElement.setAttribute("data-theme", "light");
    themeToggleBtn.setAttribute("aria-checked", "false");
  } else {
    htmlElement.setAttribute("data-theme", "dark");
    themeToggleBtn.setAttribute("aria-checked", "true");
  }
}

if (themeToggleBtn) {
  themeToggleBtn.addEventListener("click", toggleDarkMode);
}


/* ============================================================
   SECTION 2: SIDEBAR TOGGLE (FOR MOBILE)
   On small screens, the sidebar is hidden by default and
   slides in when the user taps a menu button.
   This just adds/removes a CSS class — the actual sliding
   animation lives in style.css.

   NOTE: Add a button with id="sidebarToggle" in your HTML
   (for example a hamburger icon in the topbar) to activate this.
   ============================================================ */

function toggleSidebar() {
  sidebar.classList.toggle("sidebar--open");
}

if (sidebarToggleBtn && sidebar) {
  sidebarToggleBtn.addEventListener("click", toggleSidebar);
}

// Bonus: clicking outside the open sidebar closes it (mobile only)
document.addEventListener("click", function (event) {
  var sidebarIsOpen = sidebar.classList.contains("sidebar--open");
  var clickedInsideSidebar = sidebar.contains(event.target);
  var clickedToggleButton = sidebarToggleBtn && sidebarToggleBtn.contains(event.target);

  if (sidebarIsOpen && !clickedInsideSidebar && !clickedToggleButton) {
    sidebar.classList.remove("sidebar--open");
  }
});


/* ============================================================
   SECTION 2B: COLLAPSE/EXPAND THE DOCUMENTS SECTION
   Clicking the "Documents" header (or its chevron arrow) hides
   or shows the document grid below it. The arrow rotates to
   match, using the aria-expanded attribute the CSS already
   watches for.
   ============================================================ */

function toggleDocumentsSection() {
  var isCurrentlyExpanded = docsToggle.getAttribute("aria-expanded") === "true";
  var willBeExpanded = !isCurrentlyExpanded;

  docsToggle.setAttribute("aria-expanded", String(willBeExpanded));
  docsBody.hidden = !willBeExpanded;
}

if (docsToggle) {
  docsToggle.addEventListener("click", toggleDocumentsSection);
}


/* ============================================================
   SECTION 3: FILE SELECTION
   Three different buttons (Upload, paperclip, "browse files")
   all open the SAME hidden file input. This keeps the logic
   in one place instead of repeating it three times.
   ============================================================ */

function openFileBrowser() {
  fileInput.click();
}

if (uploadBtn) {
  uploadBtn.addEventListener("click", openFileBrowser);
}

if (attachBtn) {
  attachBtn.addEventListener("click", openFileBrowser);
}

if (browseBtn) {
  browseBtn.addEventListener("click", openFileBrowser);
}

// When the user actually picks files from the system dialog
if (fileInput) {
  fileInput.addEventListener("change", function () {
    var chosenFiles = fileInput.files;

    if (chosenFiles.length > 0) {
      handleSelectedFiles(chosenFiles);
    }

    // Reset the input so selecting the same file again still fires "change"
    fileInput.value = "";
  });
}


/* ============================================================
   SECTION 4: DRAG & DROP UPLOAD UI
   We listen for drag events on the whole document so the user
   can drop a file anywhere on the page, not just on the
   dropzone box itself.
   ============================================================ */

var dragCounter = 0; // tracks nested drag-enter/leave events so the overlay doesn't flicker

function showDragOverlay() {
  if (dragOverlay) {
    dragOverlay.hidden = false;
  }
}

function hideDragOverlay() {
  if (dragOverlay) {
    dragOverlay.hidden = true;
  }
  dragCounter = 0;
}

document.addEventListener("dragenter", function (event) {
  event.preventDefault();
  dragCounter = dragCounter + 1;
  showDragOverlay();
});

document.addEventListener("dragover", function (event) {
  // Must call preventDefault, otherwise the browser will try to open the file instead of letting us drop it
  event.preventDefault();
});

document.addEventListener("dragleave", function (event) {
  event.preventDefault();
  dragCounter = dragCounter - 1;

  if (dragCounter <= 0) {
    hideDragOverlay();
  }
});

document.addEventListener("drop", function (event) {
  event.preventDefault();
  hideDragOverlay();

  var droppedFiles = event.dataTransfer.files;

  if (droppedFiles.length > 0) {
    handleSelectedFiles(droppedFiles);
  }
});

// Clicking the dropzone box itself also opens the file browser
if (dropzone) {
  dropzone.addEventListener("click", openFileBrowser);
}


/* ============================================================
   SECTION 5: HANDLE SELECTED FILES + UPLOAD PROGRESS (PLACEHOLDER)
   This function runs whether the files came from drag-drop OR
   the file picker. Right now there is no backend, so we just
   simulate a progress bar filling up over a couple of seconds.
   ============================================================ */

var allowedFileTypes = [".pdf", ".docx", ".txt", ".md"];
var maxFileSizeMB = 25;

function handleSelectedFiles(fileList) {
  var i;

  for (i = 0; i < fileList.length; i++) {
    var file = fileList[i];

    if (isValidFile(file)) {
      uploadFile(file);
    } else {
      showToast("\"" + file.name + "\" was not uploaded. Use PDF, DOCX, TXT, or MD under 25 MB.");
    }
  }
}

// Basic validation: correct file type and under the size limit
function isValidFile(file) {
  var fileName = file.name.toLowerCase();
  var hasValidExtension = false;
  var j;

  for (j = 0; j < allowedFileTypes.length; j++) {
    if (fileName.endsWith(allowedFileTypes[j])) {
      hasValidExtension = true;
    }
  }

  var fileSizeMB = file.size / (1024 * 1024);
  var isUnderSizeLimit = fileSizeMB <= maxFileSizeMB;

  return hasValidExtension && isUnderSizeLimit;
}

// Uploads one file to Flask's /upload route using XMLHttpRequest
// (not fetch) because XMLHttpRequest gives us real upload progress
// events, which fetch does not support well yet.
function uploadFile(file) {
  showToast("Uploading \"" + file.name + "\"…");

  var formData = new FormData();
  formData.append("file", file);

  var request = new XMLHttpRequest();
  request.open("POST", "/upload");

  request.upload.addEventListener("progress", function (event) {
    if (event.lengthComputable) {
      var percent = Math.round((event.loaded / event.total) * 100);
      console.log(file.name + " upload progress: " + percent + "%");
    }
  });

  request.addEventListener("load", function () {
    if (request.status >= 200 && request.status < 300) {
      showToast("\"" + file.name + "\" uploaded and indexed successfully.");
      // Refresh the document library and stats so the new file shows up.
      loadDocuments();
      loadStats();
    } else {
      var errorMessage = "Upload failed for \"" + file.name + "\".";
      try {
        var responseData = JSON.parse(request.responseText);
        if (responseData.error) {
          errorMessage = responseData.error;
        }
      } catch (parseError) {
        // Response wasn't JSON (likely a server error page) — keep the default message.
      }
      showToast(errorMessage);
    }
  });

  request.addEventListener("error", function () {
    showToast("Network error while uploading \"" + file.name + "\".");
  });

  request.send(formData);
}


/* ============================================================
   SECTION 6: SUGGESTED QUESTION CLICK
   Each suggestion chip has a data-question attribute holding
   the question text. Clicking it fills the chat input and
   sends it right away.
   ============================================================ */

if (suggestions) {
  suggestions.addEventListener("click", function (event) {
    // event.target might be the <span> inside the button, so we
    // use closest() to find the actual button that was clicked.
    var clickedChip = event.target.closest(".chip");

    if (clickedChip) {
      var question = clickedChip.getAttribute("data-question");
      chatInput.value = question;
      updateSendButtonState();
      sendChatMessage(question);
    }
  });
}


/* ============================================================
   SECTION 7: BASIC FORM VALIDATION
   The send button stays disabled until there is real text
   (not just spaces) in the chat input.
   ============================================================ */

function updateSendButtonState() {
  var messageText = chatInput.value.trim();
  sendBtn.disabled = messageText.length === 0;
}

if (chatInput) {
  chatInput.addEventListener("input", function () {
    updateSendButtonState();
    autoResizeTextarea();
  });

  // Pressing Enter sends the message; Shift+Enter makes a new line
  chatInput.addEventListener("keydown", function (event) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      chatForm.requestSubmit(); // triggers the form's "submit" event below
    }
  });
}

// Textarea grows taller as the user types more lines (up to a max set in CSS)
function autoResizeTextarea() {
  chatInput.style.height = "auto";
  chatInput.style.height = chatInput.scrollHeight + "px";
}


/* ============================================================
   SECTION 8: CHAT SEND BUTTON
   Handles the form submit event (works for both clicking the
   send button AND pressing Enter, since both trigger "submit").
   ============================================================ */

if (chatForm) {
  chatForm.addEventListener("submit", function (event) {
    event.preventDefault();

    var messageText = chatInput.value.trim();

    // Basic validation: don't send empty messages
    if (messageText.length === 0) {
      return;
    }

    sendChatMessage(messageText);
  });
}

function sendChatMessage(messageText) {
  hideEmptyState();
  addUserMessage(messageText);

  // Clear and reset the input box
  chatInput.value = "";
  chatInput.style.height = "auto";
  updateSendButtonState();

  showLoadingIndicator();

  // Send the question to our Flask backend's /chat route.
  // That route calls services/rag.py, which asks Gemini for a real,
  // document-grounded answer.
  fetch("/chat", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ question: messageText }),
  })
    .then(function (response) {
      return response.json();
    })
    .then(function (data) {
      hideLoadingIndicator();

      if (data.error) {
        showToast(data.error);
        return;
      }

      addAIMessage(data.answer, data.sources);
      loadMemoryStatus();
      loadActivity();
    })
    .catch(function (error) {
      hideLoadingIndicator();
      showToast("Something went wrong talking to the server. Please try again.");
      console.error("Chat request failed:", error);
    });
}

// Creates a right-aligned user bubble using the tplMessageUser template
function addUserMessage(messageText) {
  var messageNode = tplMessageUser.content.cloneNode(true);
  var bubble = messageNode.querySelector(".msg__bubble");

  // textContent (not innerHTML) keeps this safe from accidental HTML injection
  bubble.textContent = messageText;

  chatMessages.appendChild(messageNode);
  scrollChatToBottom();
}

// Creates a left-aligned AI bubble using the tplMessageAI template.
// "sources" is optional — an array of {filename, chunk_index, snippet, relevance_score}
// coming straight from services/rag.py's response.
function addAIMessage(messageText, sources) {
  var messageNode = tplMessageAI.content.cloneNode(true);
  var contentEl = messageNode.querySelector(".msg__content");

  // The AI's reply often contains Markdown (**bold**, * bullet lists, etc.)
  // We render that as real HTML instead of showing the raw asterisks.
  contentEl.innerHTML = renderMarkdown(messageText);

  if (sources && sources.length > 0) {
    renderSources(messageNode, sources);
  }

  chatMessages.appendChild(messageNode);
  scrollChatToBottom();
}

// Escapes HTML special characters so nothing in the AI's text can be
// interpreted as real HTML tags before we add our OWN safe formatting tags.
function escapeHtml(text) {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

// Applies inline Markdown formatting (bold, italic, inline code) to a
// single line of already-escaped text.
function applyInlineMarkdown(text) {
  var result = text;
  result = result.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
  result = result.replace(/`(.+?)`/g, "<code>$1</code>");
  result = result.replace(/(^|[^*])\*(?!\*)(.+?)\*(?!\*)/g, "$1<em>$2</em>");
  return result;
}

// A small, safe Markdown-to-HTML converter. It only understands the
// handful of things Gemini's answers actually use: **bold**, *italic*,
// `code`, and "* " or "- " bullet lists. Everything is HTML-escaped
// FIRST, so the only tags that can ever appear are the ones we add
// ourselves below — this is what keeps it safe to use with innerHTML.
function renderMarkdown(rawText) {
  var lines = escapeHtml(rawText).split("\n");
  var htmlParts = [];
  var isInsideList = false;
  var i;

  for (i = 0; i < lines.length; i++) {
    var line = lines[i];
    var isListItem = /^(\*|-)\s+/.test(line);

    if (isListItem) {
      if (!isInsideList) {
        htmlParts.push("<ul>");
        isInsideList = true;
      }
      var itemText = line.replace(/^(\*|-)\s+/, "");
      htmlParts.push("<li>" + applyInlineMarkdown(itemText) + "</li>");
    } else {
      if (isInsideList) {
        htmlParts.push("</ul>");
        isInsideList = false;
      }
      if (line.trim() !== "") {
        htmlParts.push("<p>" + applyInlineMarkdown(line) + "</p>");
      }
    }
  }

  if (isInsideList) {
    htmlParts.push("</ul>");
  }

  return htmlParts.join("");
}

// Fills in the "Sources · N" block inside an AI message using the
// tplSourceCard template — one card per retrieved chunk.
function renderSources(messageNode, sources) {
  var sourcesWrapper = messageNode.querySelector(".msg__sources");
  var sourcesCountEl = messageNode.querySelector(".msg__sources-count");
  var sourcesRow = messageNode.querySelector(".msg__sources-row");

  sourcesWrapper.hidden = false;
  sourcesCountEl.textContent = sources.length;

  var i;
  for (i = 0; i < sources.length; i++) {
    var source = sources[i];
    var cardNode = tplSourceCard.content.cloneNode(true);

    var nameEl = cardNode.querySelector(".source-card__name");
    var scoreEl = cardNode.querySelector(".source-card__score");
    var metaEl = cardNode.querySelector(".source-card__meta");
    var snippetEl = cardNode.querySelector(".source-card__snippet");

    nameEl.textContent = source.filename;
    scoreEl.textContent = source.relevance_score + "%";
    metaEl.textContent = "Chunk " + source.chunk_index;
    snippetEl.textContent = source.snippet;

    sourcesRow.appendChild(cardNode);
  }
}


/* ============================================================
   SECTION 9: LOADING INDICATOR ("thinking" dots)
   Shown in the chat while we wait for the AI's response.
   ============================================================ */

var currentTypingIndicator = null;

function showLoadingIndicator() {
  var typingNode = tplTyping.content.cloneNode(true);
  chatMessages.appendChild(typingNode);

  // Keep a reference so we can remove exactly this element later
  currentTypingIndicator = chatMessages.querySelector(".typing:last-of-type");

  scrollChatToBottom();
}

function hideLoadingIndicator() {
  if (currentTypingIndicator) {
    currentTypingIndicator.remove();
    currentTypingIndicator = null;
  }
}


/* ============================================================
   SECTION 10: AUTO SCROLL CHAT
   Keeps the chat window scrolled to the newest message
   whenever something new is added.
   ============================================================ */

function scrollChatToBottom() {
  chatMessages.scrollTop = chatMessages.scrollHeight;
}


/* ============================================================
   HELPER: HIDE THE "ASK ANYTHING" EMPTY STATE
   Runs once, the first time a message is sent.
   ============================================================ */

function hideEmptyState() {
  if (chatEmpty) {
    chatEmpty.style.display = "none";
  }
}

// Removes all message/typing bubbles from the chat window and brings
// back the "Ask anything" empty state. Used when starting a New Chat,
// switching to a different conversation, or clearing memory.
function clearChatMessagesUI() {
  var bubbles = chatMessages.querySelectorAll(".msg, .typing");
  bubbles.forEach(function (bubble) {
    bubble.remove();
  });

  if (chatEmpty) {
    chatEmpty.style.display = "";
  }
}


/* ============================================================
   HELPER: SIMPLE TOAST NOTIFICATIONS
   Used by the upload flow to give quick feedback messages.
   ============================================================ */

var toastsContainer = document.getElementById("toasts");
var tplToast = document.getElementById("tplToast");

function showToast(message) {
  if (!toastsContainer || !tplToast) {
    return;
  }

  var toastNode = tplToast.content.cloneNode(true);
  var toastEl = toastNode.querySelector(".toast");
  var messageEl = toastNode.querySelector(".toast__msg");
  var closeBtn = toastNode.querySelector(".toast__close");

  messageEl.textContent = message;

  closeBtn.addEventListener("click", function () {
    toastEl.remove();
  });

  toastsContainer.appendChild(toastNode);

  // Auto-dismiss after 4 seconds
  setTimeout(function () {
    if (toastEl.parentNode) {
      toastEl.remove();
    }
  }, 4000);
}


/* ============================================================
   SECTION 11: LOAD REAL DOCUMENTS + STATS FROM THE SERVER
   Runs on page load (and again after any upload/delete/reprocess)
   so the dashboard always reflects what's actually indexed,
   instead of showing empty placeholder values.
   ============================================================ */

function loadDocuments() {
  fetch("/documents")
    .then(function (response) {
      return response.json();
    })
    .then(function (data) {
      renderDocumentList(data.documents);
      renderRecentUploads(data.documents.slice(0, 4));
    })
    .catch(function (error) {
      console.error("Failed to load documents:", error);
    });
}

function loadStats() {
  fetch("/stats")
    .then(function (response) {
      return response.json();
    })
    .then(function (data) {
      renderStats(data);
    })
    .catch(function (error) {
      console.error("Failed to load stats:", error);
    });
}

// Clears the doc grid and rebuilds it from the server's document list.
// Shows the dropzone empty state instead if there are no documents yet.
function renderDocumentList(documents) {
  docGrid.innerHTML = "";

  if (documents.length === 0) {
    docGrid.hidden = true;
    dropzone.style.display = "flex";
  } else {
    docGrid.hidden = false;
    dropzone.style.display = "none";

    var i;
    for (i = 0; i < documents.length; i++) {
      renderDocumentCard(documents[i]);
    }
  }

  docCount.textContent = documents.length;
}

// Builds one document card from the tplDocCard template and wires up
// its "Reprocess" and "Delete" menu actions.
function renderDocumentCard(doc) {
  var cardNode = tplDocCard.content.cloneNode(true);

  var nameEl = cardNode.querySelector(".doc-card__name");
  var metaEl = cardNode.querySelector(".doc-card__meta");
  var statusLabelEl = cardNode.querySelector(".status-chip__label");
  var statusChipEl = cardNode.querySelector(".status-chip");
  var menuBtn = cardNode.querySelector("[data-action='menu']");
  var menu = cardNode.querySelector(".doc-menu");
  var viewBtn = cardNode.querySelector("[data-action='view']");
  var reprocessBtn = cardNode.querySelector("[data-action='reprocess']");
  var deleteBtn = cardNode.querySelector("[data-action='delete']");

  nameEl.textContent = doc.filename;
  metaEl.textContent = formatFileSize(doc.size_bytes) + " · " + doc.chunk_count + " chunks";
  statusLabelEl.textContent = "Indexed";
  statusChipEl.classList.add("status-chip--indexed");

  // Toggle the kebab menu open/closed
  menuBtn.addEventListener("click", function (event) {
    event.stopPropagation();
    var isOpen = !menu.hidden;
    menu.hidden = isOpen;
    menuBtn.setAttribute("aria-expanded", String(!isOpen));
  });

  viewBtn.addEventListener("click", function () {
    menu.hidden = true;
    window.open("/view/" + doc.document_id, "_blank");
  });

  reprocessBtn.addEventListener("click", function () {
    menu.hidden = true;
    reprocessDocument(doc.document_id, doc.filename);
  });

  deleteBtn.addEventListener("click", function () {
    menu.hidden = true;
    openConfirmModal(
      "Delete this document?",
      "\"" + doc.filename + "\" will be removed from the knowledge base and can't be undone.",
      function () {
        deleteDocument(doc.document_id, doc.filename);
      }
    );
  });

  docGrid.appendChild(cardNode);
}

// Turns a raw byte count into a readable size like "1.2 MB"
function formatFileSize(bytes) {
  if (bytes < 1024) {
    return bytes + " B";
  }
  if (bytes < 1024 * 1024) {
    return Math.round(bytes / 1024) + " KB";
  }
  return (bytes / (1024 * 1024)).toFixed(1) + " MB";
}

// Turns an ISO timestamp like "2026-07-10T14:32:01" into "5m ago", "2h ago", etc.
function formatRelativeTime(isoString) {
  if (!isoString) {
    return "";
  }

  var uploadedDate = new Date(isoString);
  var secondsAgo = Math.round((Date.now() - uploadedDate.getTime()) / 1000);

  if (secondsAgo < 60) {
    return "just now";
  }
  if (secondsAgo < 3600) {
    return Math.floor(secondsAgo / 60) + "m ago";
  }
  if (secondsAgo < 86400) {
    return Math.floor(secondsAgo / 3600) + "h ago";
  }
  return Math.floor(secondsAgo / 86400) + "d ago";
}

// Fills the right panel's "Recent Uploads" list with the most recent
// documents (already sorted newest-first by the backend).
function renderRecentUploads(documents) {
  recentUploadsList.innerHTML = "";

  if (documents.length === 0) {
    uploadsEmpty.hidden = false;
    return;
  }

  uploadsEmpty.hidden = true;

  var i;
  for (i = 0; i < documents.length; i++) {
    var doc = documents[i];
    var itemNode = tplUploadItem.content.cloneNode(true);

    itemNode.querySelector(".upload-item__name").textContent = doc.filename;
    itemNode.querySelector(".upload-item__time").textContent = formatRelativeTime(doc.uploaded_at);

    recentUploadsList.appendChild(itemNode);
  }
}

// Turns raw usage into a bar-fill percentage. Real usage always shows
// at least a small visible sliver (3%), even if the true percentage
// would round down to 0 — an empty-looking bar next to a non-zero
// number ("5.6 MB used") reads as broken, not as "barely anything."
function calculateStorageBarPercent(usedBytes, limitBytes) {
  var truePercent = (usedBytes / limitBytes) * 100;

  if (usedBytes > 0 && truePercent < 3) {
    return 3;
  }

  return Math.min(100, Math.round(truePercent));
}

// Fills in the four statistics cards, the storage bar, and the
// Knowledge Base panel's vector count.
function renderStats(stats) {
  var documentsValueEl = document.querySelector("[data-stat='documents'] .stat-card__value");
  var chunksValueEl = document.querySelector("[data-stat='chunks'] .stat-card__value");
  var conversationsValueEl = document.querySelector("[data-stat='conversations'] .stat-card__value");
  var storageValueEl = document.querySelector("[data-stat='storage'] .stat-card__value");
  var storageBarFillEl = document.querySelector("[data-stat='storage'] .stat-card__bar-fill");

  documentsValueEl.textContent = stats.total_documents;
  chunksValueEl.textContent = stats.total_chunks;
  conversationsValueEl.textContent = stats.total_conversations;
  storageValueEl.textContent = formatFileSize(stats.storage_used_bytes);

  // A 500 MB soft limit is more realistic for this app than 10 GB —
  // documents are only a few MB each, so a 10 GB cap made the bar
  // round down to 0% even with real files uploaded.
  var storageLimitBytes = 500 * 1024 * 1024;
  var storagePercent = calculateStorageBarPercent(stats.storage_used_bytes, storageLimitBytes);
  storageBarFillEl.style.width = storagePercent + "%";

  // Sidebar storage widget
  var storageFillEl = document.getElementById("storageFill");
  var storageValueLabelEl = document.getElementById("storageValue");
  if (storageFillEl) {
    storageFillEl.style.width = storagePercent + "%";
  }
  if (storageValueLabelEl) {
    storageValueLabelEl.textContent = formatFileSize(stats.storage_used_bytes) + " / 500 MB";
  }

  // Knowledge Base panel
  if (kbVectors) {
    kbVectors.textContent = stats.total_chunks;
  }
}


/* ============================================================
   SECTION 12: DELETE + REPROCESS A DOCUMENT
   ============================================================ */

function deleteDocument(documentId, filename) {
  fetch("/delete/" + documentId, { method: "DELETE" })
    .then(function (response) {
      return response.json();
    })
    .then(function (data) {
      if (data.error) {
        showToast(data.error);
        return;
      }
      showToast("\"" + filename + "\" deleted.");
      loadDocuments();
      loadStats();
      loadActivity();
    })
    .catch(function (error) {
      showToast("Something went wrong deleting that document.");
      console.error("Delete failed:", error);
    });
}

function reprocessDocument(documentId, filename) {
  showToast("Reprocessing \"" + filename + "\"…");

  fetch("/reprocess/" + documentId, { method: "POST" })
    .then(function (response) {
      return response.json();
    })
    .then(function (data) {
      if (data.error) {
        showToast(data.error);
        return;
      }
      showToast("\"" + filename + "\" reprocessed.");
      loadDocuments();
      loadStats();
      loadActivity();
    })
    .catch(function (error) {
      showToast("Something went wrong reprocessing that document.");
      console.error("Reprocess failed:", error);
    });
}


/* ============================================================
   SECTION 13: CONFIRM MODAL
   A single reusable modal for any "are you sure?" action
   (deleting a document, clearing memory).
   ============================================================ */

var confirmModalCallback = null;

function openConfirmModal(title, message, onConfirm) {
  modalTitle.textContent = title;
  modalMessage.textContent = message;
  confirmModalCallback = onConfirm;
  modal.hidden = false;
}

function closeConfirmModal() {
  modal.hidden = true;
  confirmModalCallback = null;
}

if (modalCancel) {
  modalCancel.addEventListener("click", closeConfirmModal);
}

// Clicking the dimmed backdrop also cancels (any element with data-close)
document.querySelectorAll("[data-close]").forEach(function (closeTarget) {
  closeTarget.addEventListener("click", closeConfirmModal);
});

if (modalConfirm) {
  modalConfirm.addEventListener("click", function () {
    if (confirmModalCallback) {
      confirmModalCallback();
    }
    closeConfirmModal();
  });
}


/* ============================================================
   SECTION 14: CLEAR CONVERSATION MEMORY
   ============================================================ */

if (clearMemoryBtn) {
  clearMemoryBtn.addEventListener("click", function () {
    openConfirmModal(
      "Clear conversation memory?",
      "This session's chat history will be forgotten. This can't be undone.",
      function () {
        fetch("/clear-memory", { method: "POST" })
          .then(function (response) {
            return response.json();
          })
          .then(function () {
            showToast("Memory cleared.");
            loadMemoryStatus();
            clearChatMessagesUI();
          })
          .catch(function (error) {
            showToast("Something went wrong clearing memory.");
            console.error("Clear memory failed:", error);
          });
      }
    );
  });
}



/* ============================================================
   SECTION 15: CONVERSATION MEMORY STATUS
   Keeps the "Conversation Memory" panel showing real numbers
   instead of always looking empty.
   ============================================================ */

function loadMemoryStatus() {
  fetch("/memory")
    .then(function (response) {
      return response.json();
    })
    .then(function (data) {
      renderMemoryStatus(data);
    })
    .catch(function (error) {
      console.error("Failed to load memory status:", error);
    });
}

function renderMemoryStatus(data) {
  if (data.message_count === 0) {
    memorySummary.textContent = "Memory is empty. Start a conversation to build context.";
  } else {
    memorySummary.textContent =
      "This session has " + data.message_count + " message(s) saved. " +
      "Follow-up questions can reference what's already been discussed.";
  }

  memoryCount.textContent = data.message_count + " / " + data.max_messages + " messages";

  var percent = Math.min(100, Math.round((data.message_count / data.max_messages) * 100));
  memoryFill.style.width = percent + "%";
}


/* ============================================================
   SECTION 16: RECENT ACTIVITY
   ============================================================ */

function loadActivity() {
  fetch("/activity")
    .then(function (response) {
      return response.json();
    })
    .then(function (data) {
      renderActivityList(data.activity);
    })
    .catch(function (error) {
      console.error("Failed to load activity:", error);
    });
}

function renderActivityList(activityItems) {
  activityList.innerHTML = "";

  if (activityItems.length === 0) {
    activityEmpty.hidden = false;
    return;
  }

  activityEmpty.hidden = true;

  var i;
  for (i = 0; i < activityItems.length; i++) {
    var item = activityItems[i];
    var itemNode = tplActivityItem.content.cloneNode(true);

    var dotEl = itemNode.querySelector(".activity__dot");
    var deleteBtn = itemNode.querySelector("[data-action='delete']");
    itemNode.querySelector(".activity__text").textContent = item.text;
    itemNode.querySelector(".activity__time").textContent = item.timestamp;

    // Color the dot based on what kind of event this was.
    dotEl.style.background = getActivityColor(item.event_type);

    // Clicking the dot (it turns into a trash icon on hover) deletes this entry.
    deleteBtn.addEventListener("click", function () {
      deleteActivityEntry(item.id);
    });

    activityList.appendChild(itemNode);
  }
}

// Deletes one activity entry, then refreshes the list.
function deleteActivityEntry(activityId) {
  fetch("/activity/" + activityId, { method: "DELETE" })
    .then(function (response) {
      return response.json();
    })
    .then(function (data) {
      if (data.error) {
        showToast(data.error);
        return;
      }
      loadActivity();
    })
    .catch(function (error) {
      showToast("Something went wrong removing that activity entry.");
      console.error("Delete activity failed:", error);
    });
}

// Picks a CSS variable to color-code each activity type's dot.
function getActivityColor(eventType) {
  if (eventType === "delete") {
    return "var(--danger)";
  }
  if (eventType === "chat") {
    return "var(--cyan)";
  }
  if (eventType === "reprocess") {
    return "var(--amber)";
  }
  return "var(--indigo)"; // upload, or anything else
}


/* ============================================================
   SECTION 17: SIDEBAR NAV + "VIEW ALL" LINK
   The app is a single dashboard page — there aren't separate
   Documents/Conversations/Settings pages yet. For now, clicking
   "Documents" (or "View all") scrolls to the document library,
   and clicking Conversations/Settings shows a short explanation
   instead of silently doing nothing.
   ============================================================ */

navLinksWithView.forEach(function (link) {
  link.addEventListener("click", function (event) {
    var view = link.getAttribute("data-view");

    if (view === "documents") {
      event.preventDefault();
      showDashboardView();
      document.getElementById("documentsSection").scrollIntoView({ behavior: "smooth" });
      setActiveNavItem(view);
    } else if (view === "dashboard") {
      event.preventDefault();
      showDashboardView();
      chatMessages.scrollIntoView({ behavior: "smooth" });
      setActiveNavItem(view);
    } else if (view === "conversations") {
      event.preventDefault();
      showConversationsView();
      setActiveNavItem(view);
    } else if (view === "settings") {
      event.preventDefault();
      showSettingsView();
      setActiveNavItem(view);
    }
  });
});

// Shows the main dashboard (stats/documents/chat), hides the others.
function showDashboardView() {
  dashboardView.hidden = false;
  settingsView.hidden = true;
  conversationsView.hidden = true;
}

// Shows the Settings view, hides the others.
function showSettingsView() {
  dashboardView.hidden = true;
  settingsView.hidden = false;
  conversationsView.hidden = true;
  loadSettings();
}

// Shows the Conversations view, hides the others.
function showConversationsView() {
  dashboardView.hidden = true;
  settingsView.hidden = true;
  conversationsView.hidden = false;
  loadConversations();
}

// Highlights whichever sidebar nav item matches the current view.
function setActiveNavItem(view) {
  document.querySelectorAll(".nav-item").forEach(function (item) {
    item.classList.remove("nav-item--active");
    item.removeAttribute("aria-current");
  });

  var activeItem = document.querySelector(".nav-item[data-view='" + view + "']");
  if (activeItem) {
    activeItem.classList.add("nav-item--active");
    activeItem.setAttribute("aria-current", "page");
  }
}


/* ============================================================
   SECTION 18: SETTINGS VIEW
   Shows the real AI models/vector database this app is running,
   and lets the user export their chat history as a PDF.
   ============================================================ */

function loadSettings() {
  fetch("/settings")
    .then(function (response) {
      return response.json();
    })
    .then(function (data) {
      settingsEmbeddingModel.textContent = data.embedding_model;
      settingsLlmProvider.textContent = data.llm_provider;
      settingsVectorDb.textContent = data.vector_database;
    })
    .catch(function (error) {
      console.error("Failed to load settings:", error);
    });
}

if (exportPdfBtn) {
  exportPdfBtn.addEventListener("click", function () {
    fetch("/export-pdf")
      .then(function (response) {
        if (!response.ok) {
          return response.json().then(function (data) {
            throw new Error(data.error || "Export failed.");
          });
        }
        return response.blob();
      })
      .then(function (pdfBlob) {
        var downloadUrl = URL.createObjectURL(pdfBlob);
        var link = document.createElement("a");
        link.href = downloadUrl;
        link.download = "conversation.pdf";
        document.body.appendChild(link);
        link.click();
        link.remove();
        URL.revokeObjectURL(downloadUrl);
      })
      .catch(function (error) {
        showToast(error.message);
      });
  });
}


/* ============================================================
   SECTION 19: CONVERSATIONS (NEW CHAT, SWITCH, DELETE)
   ============================================================ */

function loadConversations() {
  fetch("/conversations")
    .then(function (response) {
      return response.json();
    })
    .then(function (data) {
      renderConversationList(data.conversations);
    })
    .catch(function (error) {
      console.error("Failed to load conversations:", error);
    });
}

function renderConversationList(conversations) {
  conversationList.innerHTML = "";

  if (conversations.length === 0) {
    conversationsEmpty.hidden = false;
    return;
  }

  conversationsEmpty.hidden = true;

  var i;
  for (i = 0; i < conversations.length; i++) {
    renderConversationItem(conversations[i]);
  }
}

function renderConversationItem(conversation) {
  var itemNode = tplConversationItem.content.cloneNode(true);
  var itemEl = itemNode.querySelector(".conversation-item");
  var deleteBtn = itemNode.querySelector("[data-action='delete']");

  itemNode.querySelector(".conversation-item__title").textContent = conversation.title;
  itemNode.querySelector(".conversation-item__meta").textContent =
    conversation.message_count + " messages · " + formatRelativeTime(conversation.updated_at);

  if (conversation.is_active) {
    itemEl.classList.add("conversation-item--active");
  }

  // Clicking the row (but not the delete button) opens that conversation.
  itemEl.addEventListener("click", function (event) {
    if (!deleteBtn.contains(event.target)) {
      openConversation(conversation.conversation_id);
    }
  });

  deleteBtn.addEventListener("click", function (event) {
    event.stopPropagation();
    openConfirmModal(
      "Delete this conversation?",
      "\"" + conversation.title + "\" will be permanently deleted. This can't be undone.",
      function () {
        deleteConversationThread(conversation.conversation_id);
      }
    );
  });

  conversationList.appendChild(itemNode);
}

// Loads a past conversation's messages into the chat window and
// switches to it (so the next message sent continues THIS thread).
function openConversation(conversationId) {
  fetch("/conversations/" + conversationId)
    .then(function (response) {
      return response.json();
    })
    .then(function (data) {
      if (data.error) {
        showToast(data.error);
        return;
      }

      clearChatMessagesUI();

      if (data.messages.length > 0) {
        hideEmptyState();

        var i;
        for (i = 0; i < data.messages.length; i++) {
          var entry = data.messages[i];
          if (entry.role === "user") {
            addUserMessage(entry.message);
          } else {
            addAIMessage(entry.message);
          }
        }
      }

      showDashboardView();
      setActiveNavItem("dashboard");
      loadMemoryStatus();
    })
    .catch(function (error) {
      showToast("Something went wrong loading that conversation.");
      console.error("Load conversation failed:", error);
    });
}

function deleteConversationThread(conversationId) {
  fetch("/conversations/" + conversationId, { method: "DELETE" })
    .then(function (response) {
      return response.json();
    })
    .then(function (data) {
      if (data.error) {
        showToast(data.error);
        return;
      }

      showToast("Conversation deleted.");
      loadConversations();
      loadStats();
    })
    .catch(function (error) {
      showToast("Something went wrong deleting that conversation.");
      console.error("Delete conversation failed:", error);
    });
}

if (newChatBtn) {
  newChatBtn.addEventListener("click", function () {
    fetch("/conversations/new", { method: "POST" })
      .then(function (response) {
        return response.json();
      })
      .then(function () {
        clearChatMessagesUI();
        showDashboardView();
        setActiveNavItem("dashboard");
        chatMessages.scrollIntoView({ behavior: "smooth" });
        loadMemoryStatus();
        loadStats();
      })
      .catch(function (error) {
        showToast("Something went wrong starting a new chat.");
        console.error("New chat failed:", error);
      });
  });
}


/* ============================================================
   INITIAL SETUP
   Runs once when the page loads, to make sure everything
   starts in the correct state.
   ============================================================ */

updateSendButtonState();
loadDocuments();
loadStats();
loadMemoryStatus();
loadActivity();