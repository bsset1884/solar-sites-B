const wholeNumber = new Intl.NumberFormat("en-GB", { maximumFractionDigits: 0 });
const oneDecimal = new Intl.NumberFormat("en-GB", { maximumFractionDigits: 1 });

export const formatKwh = (value: number) => `${wholeNumber.format(value)} kWh`;
export const formatNumber = (value: number) => wholeNumber.format(value);
export const formatDecimal = (value: number) => oneDecimal.format(value);
export const formatPercent = (value: number) => `${oneDecimal.format(value)}%`;

export const MONTH_NAMES = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December",
];

/** "52,08" (Dutch keyboard habit) and "52.08" both become 52.08; "" stays empty. */
export function parseDecimal(text: string): number | null {
  const cleaned = text.trim().replace(",", ".");
  if (cleaned === "") return null;
  const value = Number(cleaned);
  return Number.isFinite(value) ? value : null;
}
