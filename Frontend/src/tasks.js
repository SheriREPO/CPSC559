// tasks.js — task definitions with their specific input fields
export const TASKS = [
  {
    category: "File Processing",
    name: "Image resizing/compression",
    icon: "🖼️",
    description: "Resize or compress an image to a target size or resolution.",
    fields: [{ type: "image", name: "image", label: "Upload Image" }],
  },
  {
    category: "Notification",
    name: "Send emails",
    icon: "✉️",
    description: "Send an email notification (welcome, alert, or custom).",
    fields: [
      { type: "text",     name: "recipient", label: "Recipient Email",  placeholder: "user@example.com" },
      { type: "text",     name: "subject",   label: "Subject",          placeholder: "Hello from DISTASK" },
      { type: "textarea", name: "message",   label: "Message",          placeholder: "Write your message here..." },
    ],
  },
  {
    category: "Notification",
    name: "Push notifications",
    icon: "🔔",
    description: "Send a push notification to a device or topic.",
    fields: [
      { type: "text",     name: "topic",   label: "Device / Topic", placeholder: "e.g. user_123 or alerts" },
      { type: "textarea", name: "message", label: "Message",        placeholder: "Notification message..." },
    ],
  },
  {
    category: "AI/ML",
    name: "Running sentiment analysis on text",
    icon: "🧠",
    description: "Analyse text and return a positive / negative / neutral score.",
    fields: [
      { type: "textarea", name: "text", label: "Text to Analyse", placeholder: "Paste or type the text you want analysed..." },
    ],
  },
  {
    category: "AI/ML",
    name: "Image classification",
    icon: "🔍",
    description: "Classify an image into one of several predefined categories.",
    fields: [{ type: "image", name: "image", label: "Upload Image" }],
  },
  {
    category: "AI/ML",
    name: "Generating summaries using an LLM API",
    icon: "📝",
    description: "Send a document or block of text to an LLM and get back a summary.",
    fields: [
      { type: "textarea", name: "text", label: "Text to Summarise", placeholder: "Paste the document or text you want summarised..." },
    ],
  },
];

export const CATEGORIES = [...new Set(TASKS.map((t) => t.category))];