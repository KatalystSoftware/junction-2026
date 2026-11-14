/** An editable element's text, kept out of Svelte's own text nodes so that what was typed is not shown twice. */
export function text(node: HTMLElement, value: string) {
  node.textContent = value
  return {
    update: (next: string) => {
      if (document.activeElement !== node) node.textContent = next
    },
  }
}
