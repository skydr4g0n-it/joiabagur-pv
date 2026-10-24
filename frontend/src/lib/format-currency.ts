const currencyFormatter = new Intl.NumberFormat('es-ES', {
  style: 'currency',
  currency: 'EUR',
});

export function formatCurrency(amount: number): string {
  return currencyFormatter.format(amount);
}

/** Gross formatted currency followed by net in parentheses, e.g. `1.234,56 € (987,65 €)`. */
export function formatGrossWithNetInParentheses(gross: number, net: number): string {
  return `${formatCurrency(gross)} (${formatCurrency(net)})`;
}
