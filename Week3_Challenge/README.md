<h1>Week 3 Challenge</h1>

<h2>Overview</h2>

<p>
Week 3 focused on building a tool-calling AI agent — one that goes beyond answering questions to actually taking action. The goal was to build "Trace," a personal productivity and task execution agent capable of managing tasks and notes, planning work, and executing multi-step workflows through a registry of tools, with human approval required before any write or irreversible action.
</p>

<p>
During this week, I designed and developed an agent that reasons over a registry of tools, decides when to call them versus answering directly, and routes every write or irreversible action through a human approval gate before it takes effect.
</p>

<h2>Week 3 Deliverables</h2>

<ul>
  <li>Trace Agent Source Code</li>
  <li>Architecture Diagram (Assignment 3)</li>
  <li>Tool Specification (Assignment 4)</li>
  <li>Agent Evaluation Dataset (Assignment 5)</li>
  <li>Experiments Report (Assignment 6)</li>
  <li>Security Review (Assignment 7)</li>
  <li>Builder Journal (Assignment 8)</li>
  <li>README Documentation</li>
  <li>Requirements.txt</li>
  <li>Screenshots</li>
  <li>Installation Guide</li>
</ul>

<h2>Main Learning Areas</h2>

<ul>
  <li>Tool-Calling AI Agents</li>
  <li>Agent Decision Logic (when to call a tool vs. answer directly)</li>
  <li>Multi-Step / Multi-Tool Workflows</li>
  <li>Human-in-the-Loop Approval Design</li>
  <li>Session Memory</li>
  <li>Execution Logging and Observability</li>
  <li>Error Handling and Execution Limits (max steps, retries, timeouts)</li>
  <li>Prompt / Tool Description Design</li>
  <li>Agent Evaluation and Experimentation</li>
  <li>Security for Agentic Systems</li>
</ul>

<h2>Project Features</h2>

<ul>
  <li>Conversational AI Workspace for managing tasks and notes</li>
  <li>Create, list, update, and complete tasks with priority, status, due date, and tags</li>
  <li>Save and search notes by keyword, category, or date range</li>
  <li>Extract action items from meeting notes into proposed tasks (with approval)</li>
  <li>Generate an ordered daily work plan from open tasks and available hours</li>
  <li>Create reminders and draft follow-up emails</li>
  <li>Human approval required before any write or irreversible action, with Approve/Reject/Edit</li>
  <li>Session memory to resolve follow-up references (e.g. "mark the second one complete")</li>
  <li>Execution Logs view for reviewing every agent run (tools called, arguments, results, duration, outcome)</li>
  <li>Dark, teal-accented "AI Workspace" interface</li>
</ul>

<h2>Technology Stack</h2>

<ul>
  <li>Python</li>
  <li>Flask</li>
  <li>LangGraph</li>
  <li>Google Gemini API</li>
  <li>Pydantic</li>
  <li>SQLite / SQLAlchemy</li>
  <li>HTML5</li>
  <li>CSS3</li>
  <li>JavaScript</li>
</ul>

<h2>Theme Choice</h2>


<p> For Week 3, I selected <strong>Teal Green</strong> as the primary theme color, carrying the same sense of trust and clarity into an agent that now takes real action on the user's behalf rather than only retrieving information. </p>


<h2>Project Architecture</h2>

<pre>
User
   ↓
Frontend (Chat + Approval UI)
   ↓
Agent API (Flask Routes)
   ↓
Agent State (LangGraph Controller)
   ↓
   ├──→ Gemini LLM (Decision Logic)
   └──→ Tool Registry
   ↓
Human Approval Gate
   ↓
   ├──→ Task Tools
   ├──→ Notes Tools
   └──→ Planning Tools
   ↓
Database (SQLite)
   ↓
Execution Logs
</pre>

<h2>Repository Contents</h2>

<ul>
  <li>Trace Agent Source Code (productivity-agent/)</li>
  <li>Agent Design Document</li>
  <li>Architecture Diagram (Assignment 3)</li>
  <li>Tool Specification (Assignment 4)</li>
  <li>Agent Evaluation Dataset (Assignment 5)</li>
  <li>Experiments Report (Assignment 6)</li>
  <li>Security Review (Assignment 7)</li>
  <li>Builder Journal (Assignment 8)</li>
  <li>Requirements.txt</li>
  <li>README.md</li>
</ul>

<h2>Project Links</h2>

<ul>

  <li>
    <strong>Trace Productivity Agent:</strong><br>
    <a href="https://github.com/maryamfatimaJ/AI-Agent-Fellowship-2026/tree/8fdc7c3016e28d62b4e1ff7b347e600c0c7c4bca/Week3_Challenge/productivity-agent">
      View Source Code
    </a>
  </li>

  <li>
    <strong>Live Application:</strong><br>
    [Add link here]
  </li>

  <li>
    <strong>Demo Video:</strong><br>
    [Add link here]
  </li>

</ul>

<h2>Learning Outcome</h2>

<p>
This challenge provided practical experience in designing a tool-calling AI agent that takes real action rather than only retrieving information. I learned how clear, well-scoped tool descriptions and structured output are what make an LLM's tool selection reliable instead of guesswork, and why a human approval gate is essential for any agent that can write to a database or send something on a user's behalf — it turns a risky autonomous action into a reviewable, reversible one. Building execution limits and a full execution log also showed me how to keep an agent's behavior observable and debuggable, so its reasoning and actions are traceable step by step rather than a black box.
</p>
