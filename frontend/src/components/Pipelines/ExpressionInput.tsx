import {
  Box,
  HStack,
  IconButton,
  Input,
  InputGroup,
  InputRightElement,
  Menu,
  MenuButton,
  MenuDivider,
  MenuGroup,
  MenuItem,
  MenuList,
  Portal,
  Text,
  Tooltip,
} from "@chakra-ui/react"
import { useEffect, useMemo, useRef, useState } from "react"
import { FiChevronDown, FiX } from "react-icons/fi"
import {
  ExprError,
  type ExprType,
  FUNCS,
  type Feature,
  evaluateAll,
  formulaText,
  parseFormula,
} from "../../utils/expression"

/** Stored while the text does not parse; blocks submit. */
export type InvalidExpression = { $invalid: string }

export const isInvalidExpression = (v: unknown): v is InvalidExpression =>
  !!v && typeof v === "object" && !Array.isArray(v) && "$invalid" in v

interface ExpressionInputProps {
  id: string
  type: ExprType
  value: unknown
  onChange: (value: unknown) => void
  /** undefined skips the unknown-attribute check */
  fields?: string[]
  features?: Feature[]
  literals?: string[]
  placeholder?: string
  inputRef?: React.Ref<HTMLInputElement>
}

type Suggestion = {
  label: string
  insert: string
  hint?: string
  literal?: boolean
}

const fmt = (n: number) =>
  Math.abs(n) >= 100 ? n.toFixed(0) : `${Number(n.toFixed(2))}`

function describe(type: ExprType, expr: unknown, features?: Feature[]): string {
  if (expr === "" || !features?.length) return ""
  const { values, fallback } = evaluateAll(type, expr, features)
  const ok = values.filter((v) => v !== null)
  const tail = fallback ? ` · ${fallback} use the default` : ""
  if (!ok.length)
    return "No sample feature produces a value; all use the default"
  if (type === "number") {
    const nums = ok.map(Number)
    const min = Math.min(...nums)
    const max = Math.max(...nums)
    const range = min === max ? fmt(min) : `${fmt(min)} to ${fmt(max)}`
    return `${range} over ${features.length} sample features${tail}`
  }
  const distinct = [...new Set(ok.map((v) => `${v}`))]
  const shown = distinct
    .slice(0, 3)
    .map((v) => `"${v}"`)
    .join(", ")
  const more = distinct.length > 3 ? ` +${distinct.length - 3} more` : ""
  return `${shown}${more}${tail}`
}

function sampleValue(name: string, features?: Feature[]) {
  const v = features?.find((f) => f.properties?.[name] != null)?.properties?.[
    name
  ]
  return v === undefined ? undefined : `${v}`
}

const fieldToken = (name: string) =>
  /^[\p{L}_][\p{L}\p{N}_]*$/u.test(name) &&
  !["lower", "upper"].includes(name.toLowerCase())
    ? name
    : `[${name}]`

const ExpressionInput = ({
  id,
  type,
  value,
  onChange,
  fields,
  features,
  literals,
  placeholder,
  inputRef,
}: ExpressionInputProps) => {
  const [text, setText] = useState(() =>
    isInvalidExpression(value) ? value.$invalid : formulaText(value, type),
  )
  const [cursor, setCursor] = useState(0)
  const [open, setOpen] = useState(false)
  const [active, setActive] = useState(0)
  const emitted = useRef<unknown>(value)
  const localRef = useRef<HTMLInputElement | null>(null)

  // react-hook-form returns clones, so compare by content
  useEffect(() => {
    if (JSON.stringify(value) === JSON.stringify(emitted.current)) return
    emitted.current = value
    setText(
      isInvalidExpression(value) ? value.$invalid : formulaText(value, type),
    )
  }, [value, type])

  const parsed = useMemo(() => {
    try {
      return {
        expr: parseFormula(text, type, fields?.length ? fields : undefined),
        error: null,
      }
    } catch (e) {
      return {
        expr: undefined,
        error: e instanceof ExprError ? e.message : `${e}`,
      }
    }
  }, [text, type, fields])

  // fields loading later can change validity
  useEffect(() => {
    const next = parsed.error ? { $invalid: text } : parsed.expr
    const prev = emitted.current
    if (isInvalidExpression(next) === isInvalidExpression(prev)) return
    emitted.current = next
    onChange(next)
  }, [parsed, text, onChange])

  function commit(nextText: string, nextCursor?: number) {
    setText(nextText)
    let next: unknown
    try {
      next = parseFormula(nextText, type, fields?.length ? fields : undefined)
    } catch {
      next = { $invalid: nextText }
    }
    emitted.current = next
    onChange(next)
    if (nextCursor !== undefined) {
      requestAnimationFrame(() => {
        localRef.current?.focus()
        localRef.current?.setSelectionRange(nextCursor, nextCursor)
        setCursor(nextCursor)
      })
    }
  }

  const options: Suggestion[] = useMemo(() => {
    const list: Suggestion[] = (fields ?? []).map((name) => ({
      label: name,
      insert: fieldToken(name),
      hint: sampleValue(name, features),
    }))
    list.push(
      ...FUNCS.map((f) => ({
        label: f,
        insert: f,
        hint: f === "$minZ" ? "lowest Z" : "highest Z",
      })),
    )
    if (type === "string") {
      list.push(
        { label: "lower()", insert: "lower(" },
        { label: "upper()", insert: "upper(" },
        ...(literals ?? []).map((v) => ({
          label: v,
          insert: JSON.stringify(v),
          literal: true,
        })),
      )
    }
    return list
  }, [fields, features, type, literals])

  const partial =
    /[$\p{L}_][\p{L}\p{N}_]*$/u.exec(text.slice(0, cursor))?.[0] ?? ""
  const suggestions = partial
    ? options
        .filter(
          (o) =>
            o.label.toLowerCase().startsWith(partial.toLowerCase()) &&
            o.label !== partial,
        )
        .slice(0, 8)
    : []
  const showSuggestions = open && suggestions.length > 0

  function insert(token: string, replace = 0, literal = false) {
    let start = cursor - replace
    if (literal && text[start - 1] === '"') start -= 1
    commit(
      text.slice(0, start) + token + text.slice(cursor),
      start + token.length,
    )
    setOpen(false)
  }

  function onKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (!showSuggestions) return
    if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      e.preventDefault()
      const step = e.key === "ArrowDown" ? 1 : -1
      setActive((active + step + suggestions.length) % suggestions.length)
    } else if (e.key === "Enter" || e.key === "Tab") {
      e.preventDefault()
      const s = suggestions[active]
      insert(s.insert, partial.length, s.literal)
    } else if (e.key === "Escape") {
      e.stopPropagation()
      setOpen(false)
    }
  }

  const summary = parsed.error ? "" : describe(type, parsed.expr, features)

  return (
    <Box pos="relative">
      <HStack gap={1}>
        <InputGroup>
          <Input
            id={id}
            ref={(el) => {
              localRef.current = el
              if (typeof inputRef === "function") inputRef(el)
            }}
            value={text}
            placeholder={placeholder}
            fontFamily="mono"
            autoComplete="off"
            spellCheck={false}
            isInvalid={!!parsed.error}
            onChange={(e) => {
              setCursor(e.target.selectionStart ?? e.target.value.length)
              setActive(0)
              setOpen(true)
              commit(e.target.value)
            }}
            onSelect={(e) => setCursor(e.currentTarget.selectionStart ?? 0)}
            onKeyDown={onKeyDown}
            onBlur={() => setTimeout(() => setOpen(false), 150)}
            pr={text ? 8 : undefined}
          />
          {text && (
            <InputRightElement>
              <IconButton
                aria-label="Clear"
                icon={<FiX />}
                size="xs"
                variant="ghost"
                onClick={() => commit("", 0)}
              />
            </InputRightElement>
          )}
        </InputGroup>
        <Menu placement="bottom-end" isLazy>
          <Tooltip label="Insert an attribute or function">
            <MenuButton
              as={IconButton}
              aria-label="Insert"
              icon={<FiChevronDown />}
              variant="outline"
            />
          </Tooltip>
          <Portal>
            <MenuList
              maxH="300px"
              overflowY="auto"
              fontSize="sm"
              zIndex="popover"
            >
              {fields?.length ? (
                <MenuGroup title="Attributes">
                  {options
                    .filter((o) => fields.includes(o.label))
                    .map((o) => (
                      <MenuItem
                        key={o.label}
                        onClick={() => insert(o.insert)}
                        fontFamily="mono"
                      >
                        <Text flex="1">{o.label}</Text>
                        {o.hint && (
                          <Text
                            color="gray.500"
                            fontSize="xs"
                            ml={3}
                            isTruncated
                            maxW="120px"
                          >
                            {o.hint}
                          </Text>
                        )}
                      </MenuItem>
                    ))}
                </MenuGroup>
              ) : (
                <Text px={3} py={1} color="gray.500" fontSize="xs">
                  No attributes loaded
                </Text>
              )}
              {literals?.length ? (
                <>
                  <MenuDivider />
                  <MenuGroup title="Values">
                    {options
                      .filter((o) => o.literal)
                      .map((o) => (
                        <MenuItem
                          key={o.label}
                          onClick={() => insert(o.insert)}
                          fontFamily="mono"
                        >
                          {o.insert}
                        </MenuItem>
                      ))}
                  </MenuGroup>
                </>
              ) : null}
              <MenuDivider />
              <MenuGroup title="Functions">
                {options
                  .filter((o) => !o.literal && !fields?.includes(o.label))
                  .map((o) => (
                    <MenuItem
                      key={o.label}
                      onClick={() => insert(o.insert)}
                      fontFamily="mono"
                    >
                      <Text flex="1">{o.label}</Text>
                      {o.hint && (
                        <Text color="gray.500" fontSize="xs" ml={3}>
                          {o.hint}
                        </Text>
                      )}
                    </MenuItem>
                  ))}
              </MenuGroup>
            </MenuList>
          </Portal>
        </Menu>
      </HStack>
      {showSuggestions && (
        <Box
          pos="absolute"
          top="34px"
          left={0}
          right="40px"
          zIndex="popover"
          bg="white"
          _dark={{ bg: "gray.700" }}
          borderWidth="1px"
          borderRadius="md"
          boxShadow="md"
          py={1}
        >
          {suggestions.map((s, i) => (
            <HStack
              key={s.label}
              px={3}
              py={1}
              cursor="pointer"
              fontFamily="mono"
              fontSize="sm"
              bg={i === active ? "gray.100" : undefined}
              _dark={{ bg: i === active ? "gray.600" : undefined }}
              onMouseDown={(e) => {
                e.preventDefault()
                insert(s.insert, partial.length, s.literal)
              }}
            >
              <Text flex="1">{s.label}</Text>
              {s.hint && (
                <Text color="gray.500" fontSize="xs" isTruncated maxW="140px">
                  {s.hint}
                </Text>
              )}
            </HStack>
          ))}
        </Box>
      )}
      {(parsed.error || summary) && (
        <Text
          fontSize="xs"
          mt={1}
          color={parsed.error ? "red.500" : "gray.500"}
        >
          {parsed.error || summary}
        </Text>
      )}
    </Box>
  )
}

export default ExpressionInput
