from __future__ import annotations

import json

from playwright.sync_api import sync_playwright

from edot_qa.config import load_settings
from edot_qa.web.session_state import new_context


TARGET_COMPANY = "PT Maju QA 73179FB9"

INSPECT_SCRIPT = r"""
(target) => {
  const normalize = (value) => String(value || "").replace(/\s+/g, " ").trim();
  const visible = (element) => {
    if (!element) return false;
    const style = window.getComputedStyle(element);
    const rect = element.getBoundingClientRect();
    return style.display !== "none" && style.visibility !== "hidden" && rect.width > 0 && rect.height > 0;
  };
  const textOf = (element) => normalize(element.innerText || element.textContent || "");
  const actionText = (element) => normalize(
    element.innerText ||
    element.textContent ||
    element.getAttribute("aria-label") ||
    element.getAttribute("title") ||
    element.value ||
    ""
  );
  const out = {url: location.href, title: document.title, headings: [], targetMatches: [], visibleButtons: []};
  out.headings = Array.from(document.querySelectorAll("h1,h2,h3,[role='heading']"))
    .filter(visible)
    .map(textOf)
    .filter(Boolean)
    .slice(0, 20);
  out.visibleButtons = Array.from(document.querySelectorAll("button,a,[role='button']"))
    .filter(visible)
    .map((element) => ({
      text: actionText(element),
      tag: element.tagName,
      cls: String(element.className || "").slice(0, 120),
    }))
    .filter((button) => button.text)
    .slice(0, 80);

  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  let node = walker.nextNode();
  while (node) {
    if (normalize(node.nodeValue) === normalize(target) && visible(node.parentElement)) {
      const chain = [];
      let container = node.parentElement;
      for (let depth = 0; container && container !== document.body && depth <= 10; depth += 1) {
        const rect = container.getBoundingClientRect();
        const actions = Array.from(container.querySelectorAll("button,a,[role='button']"))
          .filter(visible)
          .map((element) => ({
            text: actionText(element),
            tag: element.tagName,
            cls: String(element.className || "").slice(0, 120),
            x: Math.round(element.getBoundingClientRect().x),
            y: Math.round(element.getBoundingClientRect().y),
          }));
        chain.push({
          depth,
          tag: container.tagName,
          cls: String(container.className || "").slice(0, 160),
          x: Math.round(rect.x),
          y: Math.round(rect.y),
          w: Math.round(rect.width),
          h: Math.round(rect.height),
          text: textOf(container).slice(0, 300),
          actions,
        });
        container = container.parentElement;
      }
      out.targetMatches.push({
        nodeText: normalize(node.nodeValue),
        parentTag: node.parentElement.tagName,
        parentClass: String(node.parentElement.className || "").slice(0, 160),
        chain,
      });
    }
    node = walker.nextNode();
  }
  return out;
}
"""


def main() -> None:
    settings = load_settings()
    with sync_playwright() as playwright:
        browser = getattr(playwright, settings.browser).launch(headless=settings.headless, slow_mo=0)
        context = new_context(browser, settings, use_storage_state=True)
        page = context.new_page()
        page.goto("/companies")
        page.wait_for_load_state("domcontentloaded")
        page.wait_for_timeout(1500)
        data = page.evaluate(INSPECT_SCRIPT, TARGET_COMPANY)
        print(json.dumps(data, indent=2, ensure_ascii=False))
        context.close()
        browser.close()


if __name__ == "__main__":
    main()
