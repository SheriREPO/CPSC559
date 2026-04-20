// frontend/src/tasks.js

export const TASK_CATEGORIES = [
    {
      name: "File Processing",
      tasks: [
        "Image resizing/compression",
        "PDF generation from templates",
        "Video thumbnail extraction",
        "CSV parsing and validation",
        "File format conversion (docx → pdf)",
      ],
    },
    {
      name: "Notification",
      tasks: [
        "Send emails (welcome, password reset, alerts)",
        "Push notifications",
        "SMS delivery",
        "Slack/Discord webhook messages",
      ],
    },
    {
      name: "Data Processing",
      tasks: [
        "Scraping and storing web data",
        "Aggregating analytics (daily reports)",
        "Database cleanup/archiving old records",
        "Syncing data between two services (CRM → spreadsheet)",
      ],
    },
    {
      name: "AI/ML",
      tasks: [
        "Running sentiment analysis on text",
        "Image classification",
        "Generating summaries using an LLM API",
        "Batch embeddings generation",
      ],
    },
    {
      name: "Dev/DevOps",
      tasks: [
        "Running tests on code submissions",
        "Linting and formatting code",
        "Sending build status notifications",
        "Database backup jobs",
      ],
    },
  ];
  
  export const ALL_TASKS = TASK_CATEGORIES.flatMap((category) =>
    category.tasks.map((task) => ({
      category: category.name,
      task,
    }))
  );
  
  export function getTasksByCategory(categoryName) {
    const category = TASK_CATEGORIES.find((item) => item.name === categoryName);
    return category ? category.tasks : [];
  }
  
  export function getCategoryOptions() {
    return TASK_CATEGORIES.map((category) => category.name);
  }
  
  export function isValidCategory(categoryName) {
    return TASK_CATEGORIES.some((category) => category.name === categoryName);
  }
  
  export function isValidTask(categoryName, taskName) {
    const tasks = getTasksByCategory(categoryName);
    return tasks.includes(taskName);
  }
  
  export function findTaskDetails(taskName) {
    return ALL_TASKS.find((item) => item.task === taskName) || null;
  }
  
  export const DEFAULT_TASK_FORM = {
    category: TASK_CATEGORIES[0]?.name || "",
    task: TASK_CATEGORIES[0]?.tasks?.[0] || "",
    details: "",
  };