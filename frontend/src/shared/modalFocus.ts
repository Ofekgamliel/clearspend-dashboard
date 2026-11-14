import type { ObjectDirective } from 'vue';

type FocusEntry = {
  element: HTMLElement;
  previous: HTMLElement | null;
  keydown: (event: KeyboardEvent) => void;
};

const focusStack: FocusEntry[] = [];
const focusableSelector = [
  '[data-modal-initial-focus]',
  'button:not([disabled])',
  'a[href]',
  'input:not([disabled])',
  'select:not([disabled])',
  'textarea:not([disabled])',
  '[tabindex]:not([tabindex="-1"])',
].join(',');

function visibleFocusableElements(element: HTMLElement): HTMLElement[] {
  return [...element.querySelectorAll<HTMLElement>(focusableSelector)].filter((candidate) => {
    if (candidate.hidden || candidate.getAttribute('aria-hidden') === 'true') return false;
    const style = window.getComputedStyle(candidate);
    return style.display !== 'none' && style.visibility !== 'hidden';
  });
}

function isTop(entry: FocusEntry): boolean {
  return focusStack[focusStack.length - 1] === entry;
}

export const modalFocus: ObjectDirective<HTMLElement> = {
  mounted(element) {
    const entry: FocusEntry = {
      element,
      previous: document.activeElement instanceof HTMLElement ? document.activeElement : null,
      keydown: () => undefined,
    };
    entry.keydown = (event: KeyboardEvent) => {
      if (event.key !== 'Tab' || !isTop(entry)) return;
      const focusable = visibleFocusableElements(element);
      if (!focusable.length) {
        event.preventDefault();
        element.focus();
        return;
      }
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && (document.activeElement === first || !element.contains(document.activeElement))) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };
    element.tabIndex = element.tabIndex < 0 ? -1 : element.tabIndex;
    element.addEventListener('keydown', entry.keydown);
    focusStack.push(entry);
    requestAnimationFrame(() => requestAnimationFrame(() => {
      if (!isTop(entry) || !element.isConnected) return;
      const preferred = element.querySelector<HTMLElement>('[autofocus], [data-modal-initial-focus]');
      const first = preferred ?? visibleFocusableElements(element)[0] ?? element.querySelector<HTMLElement>(focusableSelector);
      first?.focus() ?? element.focus();
    }));
    (element as HTMLElement & { __modalFocusEntry?: FocusEntry }).__modalFocusEntry = entry;
  },
  beforeUnmount(element) {
    const target = element as HTMLElement & { __modalFocusEntry?: FocusEntry };
    const entry = target.__modalFocusEntry;
    if (!entry) return;
    element.removeEventListener('keydown', entry.keydown);
    const index = focusStack.indexOf(entry);
    if (index >= 0) focusStack.splice(index, 1);
    if (entry.previous?.isConnected) requestAnimationFrame(() => entry.previous?.focus());
    delete target.__modalFocusEntry;
  },
};
