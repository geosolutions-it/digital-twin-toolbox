// formula text <-> arrays evaluated by backend/app/worker/common/expression.py

export type ExprType = "number" | "string"
export type Expr = number | string | any[]
export type Feature = {
  geometry?: { type: string; coordinates: any } | null
  properties?: Record<string, unknown> | null
}

export const FUNCS = ["$minZ", "$maxZ"]
const CALLS: Record<string, string> = { lower: "lowercase", upper: "uppercase" }
const CALL_NAMES: Record<string, string> = { lowercase: "lower", uppercase: "upper" }

export class ExprError extends Error {
  constructor(
    message: string,
    public at = -1,
  ) {
    super(message)
  }
}

type Token = { kind: "num" | "str" | "id" | "field" | "func" | "op"; text: string; value: any; at: number }

const IDENT = /[\p{L}_][\p{L}\p{N}_]*/uy
const NUMBER = /(\d+\.?\d*|\.\d+)([eE][+-]?\d+)?/y

function tokenize(text: string): Token[] {
  const tokens: Token[] = []
  let i = 0
  const at = (re: RegExp) => {
    re.lastIndex = i
    return re.exec(text)
  }
  while (i < text.length) {
    const ch = text[i]
    if (/\s/.test(ch)) {
      i++
      continue
    }
    const start = i
    const num = at(NUMBER)
    const ident = at(IDENT)
    if (num) {
      tokens.push({ kind: "num", text: num[0], value: Number(num[0]), at: start })
      i += num[0].length
    } else if (ch === '"' || ch === "'") {
      let out = ""
      i++
      while (i < text.length && text[i] !== ch) {
        if (text[i] === "\\" && i + 1 < text.length) i++
        out += text[i++]
      }
      if (i >= text.length) throw new ExprError("Unclosed quote", start)
      i++
      tokens.push({ kind: "str", text: text.slice(start, i), value: out, at: start })
    } else if (ch === "[") {
      const end = text.indexOf("]", i)
      if (end < 0) throw new ExprError("Unclosed [", start)
      tokens.push({ kind: "field", text: text.slice(start, end + 1), value: text.slice(i + 1, end), at: start })
      i = end + 1
    } else if (ch === "$") {
      i++
      const word = at(IDENT)?.[0] ?? ""
      const name = `$${word}`
      if (!FUNCS.includes(name)) throw new ExprError(`Unknown function ${name}, use ${FUNCS.join(" or ")}`, start)
      tokens.push({ kind: "func", text: name, value: name, at: start })
      i += word.length
    } else if (ident) {
      tokens.push({ kind: "id", text: ident[0], value: ident[0], at: start })
      i += ident[0].length
    } else if ("+-*/(),".includes(ch)) {
      tokens.push({ kind: "op", text: ch, value: ch, at: start })
      i++
    } else {
      throw new ExprError(`Unexpected "${ch}"`, start)
    }
  }
  return tokens
}

/** "" for an empty field; throws ExprError. */
export function parseFormula(text: string, type: ExprType, fields?: string[]): Expr {
  if (!text.trim()) return ""
  let tokens: Token[]
  try {
    tokens = tokenize(text)
  } catch (e) {
    if (type === "string" && e instanceof ExprError && !e.message.includes("quote")) {
      throw new ExprError(`${e.message}, put plain text in quotes`, e.at)
    }
    throw e
  }
  let pos = 0
  const peek = () => tokens[pos]
  const isOp = (op: string) => peek()?.kind === "op" && peek().value === op
  const expect = (op: string) => {
    if (!isOp(op)) throw new ExprError(`Expected "${op}"`, peek()?.at ?? text.length)
    pos++
  }
  const plus = type === "string" ? "concat" : "+"

  function primary(): Expr {
    const tok = peek()
    if (!tok) throw new ExprError("Incomplete formula", text.length)
    pos++
    if (tok.kind === "num" || tok.kind === "str") return tok.value
    if (tok.kind === "func") return ["func", tok.value]
    if (tok.kind === "field") return field(tok)
    if (tok.kind === "id") {
      const call = CALLS[tok.value.toLowerCase()]
      if (call && isOp("(")) {
        pos++
        const arg = sum()
        expect(")")
        return [call, arg]
      }
      return field(tok)
    }
    if (tok.value === "(") {
      const inner = sum()
      expect(")")
      return inner
    }
    throw new ExprError(`Unexpected "${tok.text}"`, tok.at)
  }

  function field(tok: Token): Expr {
    if (fields && !fields.includes(tok.value)) {
      const hint = type === "string" ? ', put plain text in quotes' : ""
      throw new ExprError(`Unknown attribute "${tok.value}"${hint}`, tok.at)
    }
    return ["property", tok.value]
  }

  function unary(): Expr {
    if (isOp("-")) {
      pos++
      const value = unary()
      return typeof value === "number" ? -value : ["-", 0, value]
    }
    return primary()
  }

  function product(): Expr {
    let left = unary()
    while (isOp("*") || isOp("/")) {
      const op = tokens[pos++].value
      left = [op, left, unary()]
    }
    return left
  }

  function sum(): Expr {
    let left = product()
    while (isOp("+") || isOp("-")) {
      const op = tokens[pos++].value
      left = [op === "+" ? plus : "-", left, product()]
    }
    return left
  }

  const result = sum()
  if (pos < tokens.length) throw new ExprError(`Unexpected "${peek().text}"`, peek().at)
  return result
}

const PRECEDENCE: Record<string, number> = { "+": 1, "-": 1, concat: 1, "*": 2, "/": 2 }

function fieldText(name: unknown): string {
  const text = `${name ?? ""}`
  return /^[\p{L}_][\p{L}\p{N}_]*$/u.test(text) && !CALLS[text.toLowerCase()] ? text : `[${text}]`
}

/** Inverse of parseFormula. */
export function formulaText(value: unknown, type: ExprType): string {
  if (value === undefined || value === null || value === "") return ""
  if (typeof value === "number") return `${value}`
  if (typeof value === "string") {
    if (type === "number" && value.trim() !== "" && !Number.isNaN(Number(value))) return value.trim()
    return JSON.stringify(value)
  }
  if (!Array.isArray(value)) return ""
  const [op, a, b] = value
  if (op === "property") return fieldText(a)
  if (op === "func") return `${a ?? ""}`
  if (CALL_NAMES[op]) return `${CALL_NAMES[op]}(${formulaText(a, type)})`
  if (op in PRECEDENCE) {
    if (op === "-" && (a === 0 || a === "0")) return `-${wrap(b, 2, type)}`
    const p = PRECEDENCE[op]
    const symbol = op === "concat" ? "+" : op
    // right operand of - and / needs parentheses at equal precedence
    const rightMin = op === "-" || op === "/" ? p + 1 : p
    return `${wrap(a, p, type)} ${symbol} ${wrap(b, rightMin, type)}`
  }
  return ""
}

function wrap(value: unknown, min: number, type: ExprType): string {
  const text = formulaText(value, type)
  const p = Array.isArray(value) ? PRECEDENCE[value[0]] : undefined
  return p !== undefined && p < min ? `(${text})` : text
}

function zRange(feature: Feature): [number, number] | null {
  const geometry = feature.geometry
  if (!geometry) return null
  let min = Number.POSITIVE_INFINITY
  let max = Number.NEGATIVE_INFINITY
  const visit = (c: any) => {
    if (typeof c[0] === "number") {
      const z = c.length === 3 ? c[2] : 0
      min = Math.min(min, z)
      max = Math.max(max, z)
    } else c.forEach(visit)
  }
  if (geometry.type === "Point" || geometry.type === "Polygon") visit(geometry.coordinates)
  return min <= max ? [min, max] : null
}

function toFloat(v: unknown): number {
  const n = typeof v === "number" ? v : typeof v === "boolean" ? Number(v) : typeof v === "string" && v.trim() ? Number(v) : Number.NaN
  if (Number.isNaN(n)) throw new Error("not a number")
  return n
}

const pyStr = (v: unknown) => (v === null || v === undefined ? "None" : `${v}`)

/** Throws where the worker falls back to the default. */
export function evaluate(type: ExprType | "", value: unknown, feature: Feature): any {
  if (!Array.isArray(value)) {
    if (value === null || value === undefined) return null
    if (type === "string") return `${value}`
    if (type === "number") return toFloat(value)
    return value
  }
  const [op] = value
  const inner = op === "property" || op === "func" ? "" : type
  const a = value.length > 1 ? evaluate(inner, value[1], feature) : null
  const b = value.length > 2 ? evaluate(inner, value[2], feature) : null
  switch (op) {
    case "+":
      return toFloat(a) + toFloat(b)
    case "-":
      return toFloat(a) - toFloat(b)
    case "*":
      return toFloat(a) * toFloat(b)
    case "/": {
      if (toFloat(b) === 0) throw new Error("division by zero")
      return toFloat(a) / toFloat(b)
    }
    case "concat":
      return `${pyStr(a)}${pyStr(b)}`
    case "lowercase":
      return pyStr(a).toLowerCase()
    case "uppercase":
      return pyStr(a).toUpperCase()
    case "property":
      return feature.properties?.[a as string] ?? null
    case "func": {
      const range = zRange(feature)
      if (!range) return null
      return a === "$maxZ" ? range[1] : range[0]
    }
    default:
      return null
  }
}

export type ExprSummary = { values: any[]; fallback: number }

/** null where the worker would use the default. */
export function evaluateAll(type: ExprType, value: unknown, features: Feature[]): ExprSummary {
  let fallback = 0
  const values = features.map((feature) => {
    try {
      const v = evaluate(type, value, feature)
      if (v === null || v === undefined || (typeof v === "number" && !Number.isFinite(v))) {
        fallback++
        return null
      }
      return v
    } catch {
      fallback++
      return null
    }
  })
  return { values, fallback }
}
