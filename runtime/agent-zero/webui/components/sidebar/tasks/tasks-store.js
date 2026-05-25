import { createStore } from "/js/AlpineStore.js";
import { store as chatsStore } from "/components/sidebar/chats/chats-store.js";
import { store as schedulerStore } from "/components/modals/scheduler/scheduler-store.js";

// Tasks sidebar store: tasks list and selected task id
const model = {
  tasks: [],
  selected: "",
  recentDropdownOpen: false,

  init() {
    // No-op: data is driven by poll() in index.js; this store provides a stable target
  },

  // Apply tasks coming from poll() and keep them sorted (newest first)
  applyTasks(tasksList) {
    try {
      const tasks = Array.isArray(tasksList) ? tasksList : [];
      const sorted = tasks
        .map((task) => this.normalizeTask(task))
        .filter(Boolean)
        .sort((a, b) => this.sortTimestamp(b) - this.sortTimestamp(a));
      this.tasks = sorted;

      // After updating tasks, ensure selection is still valid
      if (this.selected && !this.contains(this.selected)) {
        this.setSelected("");
      }
    } catch (e) {
      console.error("tasks-store.applyTasks failed", e);
      this.tasks = [];
    }
  },

  normalizeTask(task) {
    if (!task) return null;
    const id = task.id || task.uuid || task.context_id;
    if (!id) return null;
    return {
      ...task,
      id,
      uuid: task.uuid || id,
      context_id: task.context_id || id,
      task_name: task.task_name || task.name || "",
      state: task.state || "idle",
    };
  },

  sortTimestamp(item) {
    const value = item?.last_message || item?.updated_at || item?.created_at || item?.last_run;
    const time = Date.parse(value || "");
    return Number.isNaN(time) ? 0 : time;
  },

  get recentItems() {
    const itemsById = new Map();

    const addItem = (item) => {
      if (!item?.id) return;
      const existing = itemsById.get(item.id);
      if (!existing || item.timestamp > existing.timestamp || item.source === "scheduler") {
        itemsById.set(item.id, item);
      }
    };

    const contexts = Array.isArray(chatsStore.contexts) ? chatsStore.contexts : [];
    for (const context of contexts) {
      const id = context?.id;
      if (!id) continue;
      const shortId = String(id).slice(0, 6);
      addItem({
        id,
        source: "chat",
        title: context.name || `Task #${context.no || shortId}`,
        subtitle: context.project?.title || context.project?.name || "Chat task",
        timestamp: this.sortTimestamp(context),
        running: Boolean(context.running),
        project: context.project || null,
        raw: context,
      });
    }

    const tasks = Array.isArray(this.tasks) ? this.tasks : [];
    for (const task of tasks) {
      const id = task?.id || task?.uuid;
      if (!id) continue;
      const shortId = String(id).slice(0, 6);
      addItem({
        id,
        source: "scheduler",
        title: task.task_name || task.name || `Task #${task.no || shortId}`,
        subtitle: this.describeTask(task),
        timestamp: this.sortTimestamp(task),
        running: Boolean(task.running || task.state === "running"),
        project: task.project || null,
        raw: task,
      });
    }

    return Array.from(itemsById.values())
      .sort((a, b) => b.timestamp - a.timestamp)
      .slice(0, 12);
  },

  get recentTaskCount() {
    return this.recentItems.length;
  },

  get recentDropdownLabel() {
    const first = this.recentItems[0];
    return first?.title || "No recent tasks";
  },

  describeTask(task) {
    const type = task?.type ? `${task.type}` : "Task";
    const state = task?.state || "idle";
    if (task?.next_run) return `${type} - ${state} - next ${this.formatCompactDate(task.next_run)}`;
    if (task?.last_run) return `${type} - ${state} - ran ${this.formatCompactDate(task.last_run)}`;
    return `${type} - ${state}`;
  },

  formatCompactDate(value) {
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return "";
    return date.toLocaleString([], {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  },

  toggleRecentDropdown() {
    this.recentDropdownOpen = !this.recentDropdownOpen;
  },

  closeRecentDropdown() {
    this.recentDropdownOpen = false;
  },

  selectRecent(item) {
    if (!item?.id) return;
    this.closeRecentDropdown();
    if (item.source === "scheduler") {
      this.selectTask(item.id);
      return;
    }
    chatsStore.selectChat(item.id);
  },

  async createTask() {
    this.closeRecentDropdown();
    await chatsStore.newChat();
  },

  // Update selected task and persist for tab restore
  setSelected(taskId) {
    this.selected = taskId || "";
    try { localStorage.setItem("lastSelectedTask", this.selected); } catch {}
  },

  // Returns true if a task with the given id exists in the current list
  contains(taskId) {
    return Array.isArray(this.tasks) && this.tasks.some((t) => t?.id === taskId || t?.uuid === taskId || t?.context_id === taskId);
  },

  // Convenience: id of the first task in the current list (or empty string)
  firstId() {
    return (Array.isArray(this.tasks) && this.tasks[0]?.id) || "";
  },

  // Action methods for task management
  selectTask(taskId) {
    const task = this.tasks.find((t) => t?.id === taskId || t?.uuid === taskId || t?.context_id === taskId);
    this.setSelected(taskId);
    if (task?.context_available === false) {
      this.openDetail(taskId);
      return;
    }
    chatsStore.selectChat(task?.context_id || taskId);
  },

  openDetail(taskId) {
    // Open lightweight task detail popup directly
    if (schedulerStore?.showTaskDetail) {
      schedulerStore.showTaskDetail(taskId);
    }
  },

  reset(taskId) {
    chatsStore.resetChat(taskId);
  },

  deleteTask(taskId) {
    if (schedulerStore?.deleteTaskFromSidebar) {
      schedulerStore.deleteTaskFromSidebar(taskId);
    }
  },
};

export const store = createStore("tasks", model);
