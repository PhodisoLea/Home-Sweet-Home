"use strict";

document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll("[data-password-toggle]").forEach((toggle) => {
    toggle.addEventListener("click", () => {
      const input = document.getElementById(toggle.getAttribute("aria-controls"));
      if (!(input instanceof HTMLInputElement)) return;
      const showing = input.type === "password";
      input.type = showing ? "text" : "password";
      toggle.textContent = showing ? "Hide" : "Show";
      toggle.setAttribute("aria-pressed", String(showing));
      toggle.setAttribute("aria-label", `${showing ? "Hide" : "Show"} ${input.labels?.[0]?.textContent || "password"}`);
    });
  });

  const dialog = document.querySelector("#assistant-dialog");
  const openButton = document.querySelector("#assistant-open-button");
  const closeButton = document.querySelector("#assistant-close");

  if (dialog && openButton && closeButton) {
    openButton.addEventListener("click", () => dialog.showModal());
    closeButton.addEventListener("click", () => dialog.close());
  }

  document.querySelectorAll("#assistant-form").forEach((form) => {
    const messages = document.querySelector("#assistant-messages");
    const questionInput = form.elements.namedItem("question");
    if (!messages || !(questionInput instanceof HTMLInputElement)) return;
    const historyKey = `homehelp-assistant-history-${form.dataset.user || "guest"}`;
    let history = [];
    let storageAvailable = true;
    const greeting = messages.querySelector(".assistant-bubble")?.textContent
      || "Hi! Ask me about Home Help, household jobs or safety.";

    const addMessage = (text, mine, links = [], classification = "") => {
      const bubble = document.createElement("div");
      bubble.className = `assistant-bubble${mine ? " mine" : ""}`;
      bubble.textContent = text;
      if (classification) {
        const label = document.createElement("span");
        label.className = `assistant-classification ${classification}`;
        label.textContent = classification === "not_found"
          ? "Not found in Home Help"
          : classification === "unavailable"
            ? "Assistant unavailable"
            : "Home Help information";
        bubble.prepend(label);
      }
      if (links.length) {
        const linkList = document.createElement("div");
        linkList.className = "assistant-answer-links";
        links.forEach((item) => {
          const anchor = document.createElement("a");
          const target = new URL(item.url, window.location.origin);
          if (target.origin !== window.location.origin) return;
          anchor.href = target.href;
          anchor.textContent = item.label;
          linkList.append(anchor);
        });
        bubble.append(linkList);
      }
      messages.append(bubble);
      messages.scrollTop = messages.scrollHeight;
    };

    const saveHistory = () => {
      if (!storageAvailable) return;
      try {
        sessionStorage.setItem(historyKey, JSON.stringify(history));
      } catch {
        storageAvailable = false;
        addMessage("This browser couldn't save your chat history. You can continue chatting, but it may disappear when you leave this page.", false);
      }
    };

    try {
      const saved = sessionStorage.getItem(historyKey);
      if (saved) {
        const parsed = JSON.parse(saved);
        if (Array.isArray(parsed)) {
          history = parsed.filter((turn) =>
            turn
            && typeof turn.question === "string"
            && typeof turn.answer === "string"
            && typeof turn.classification === "string"
            && Array.isArray(turn.links)
          );
        }
      }
    } catch {
      storageAvailable = false;
    }

    messages.replaceChildren();
    addMessage(greeting, false);
    history.forEach((turn) => {
      addMessage(turn.question, true);
      addMessage(turn.answer, false, turn.links, turn.classification);
    });

    document.querySelectorAll("[data-assistant-clear]").forEach((clearButton) => {
      clearButton.addEventListener("click", () => {
        history = [];
        messages.replaceChildren();
        addMessage(greeting, false);
        if (storageAvailable) {
          try {
            sessionStorage.removeItem(historyKey);
          } catch {
            storageAvailable = false;
            addMessage("This browser couldn't clear the saved chat history.", false);
          }
        }
      });
    });

    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const question = questionInput.value.trim();
      if (!question) return;

      addMessage(question, true);
      questionInput.value = "";
      const submitButton = form.querySelector('button[type="submit"]');
      submitButton.disabled = true;

      try {
        const body = new FormData(form);
        body.set("question", question);
        if (form.dataset.job) body.set("job_id", form.dataset.job);
        const response = await fetch(form.dataset.endpoint, {
          method: "POST",
          body,
          headers: { "X-Requested-With": "XMLHttpRequest" },
          credentials: "same-origin",
        });
        const result = await response.json();
        if (!response.ok) throw new Error(result.error || "The guide could not answer right now.");
        const turn = {
          question,
          answer: result.answer,
          classification: result.classification || "home_help",
          links: result.links || [],
        };
        history.push(turn);
        saveHistory();
        addMessage(turn.answer, false, turn.links, turn.classification);
      } catch (error) {
        const turn = {
          question,
          answer: error instanceof Error ? error.message : "The guide could not answer right now.",
          classification: "unavailable",
          links: [],
        };
        history.push(turn);
        saveHistory();
        addMessage(turn.answer, false, [], turn.classification);
      } finally {
        submitButton.disabled = false;
        questionInput.focus();
      }
    });

  });

  document.querySelectorAll("[data-assistant-prompt]").forEach((prompt) => {
    prompt.addEventListener("click", () => {
      const form = document.querySelector("#assistant-form");
      const questionInput = form?.elements.namedItem("question");
      if (!(questionInput instanceof HTMLInputElement)) return;
      questionInput.value = prompt.dataset.assistantPrompt;
      form.requestSubmit();
    });
  });
});
