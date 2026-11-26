const PERSIAN_DIGITS = '۰۱۲۳۴۵۶۷۸۹'
const ARABIC_INDIC_DIGITS = '٠١٢٣٤٥٦٧٨٩'
const LATIN_DIGITS = '0123456789'

const TO_LATIN: Record<string, string> = {}
const TO_PERSIAN: Record<string, string> = {}

for (let i = 0; i < 10; i += 1) {
  TO_LATIN[PERSIAN_DIGITS[i]] = LATIN_DIGITS[i]
  TO_LATIN[ARABIC_INDIC_DIGITS[i]] = LATIN_DIGITS[i]
  TO_PERSIAN[LATIN_DIGITS[i]] = PERSIAN_DIGITS[i]
}

/** Map Persian and Arabic-Indic digits to Latin 0-9. Leave other characters. */
export function toLatinDigits(text: string): string {
  if (!text) return text
  return Array.from(text, (ch) => TO_LATIN[ch] ?? ch).join('')
}

/** Map Latin digits 0-9 to Persian digits. Leave other characters. */
export function toPersianDigits(text: string): string {
  if (!text) return text
  return Array.from(text, (ch) => TO_PERSIAN[ch] ?? ch).join('')
}
