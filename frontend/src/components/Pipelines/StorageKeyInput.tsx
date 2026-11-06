import {
  Box,
  HStack,
  IconButton,
  Input,
  InputGroup,
  InputRightElement,
  Popover,
  PopoverAnchor,
  PopoverContent,
  Portal,
  Spinner,
  Text,
} from "@chakra-ui/react"
import { useQuery } from "@tanstack/react-query"
import { useRef, useState } from "react"
import { FiFile, FiFolder, FiX } from "react-icons/fi"
import { listStorage } from "../../api/storageBrowser"

interface StorageKeyInputProps {
  id: string
  value?: string
  onChange: (value: string) => void
  placeholder?: string
  extensions?: string[]
  foldersOnly?: boolean
  inputRef?: React.Ref<HTMLInputElement>
}

type Entry = { key: string; name: string; folder: boolean }

export const useStorageListing = (dir: string, enabled = true) =>
  useQuery({
    queryKey: ["storage-list", dir],
    queryFn: () => listStorage(dir, false),
    enabled,
    staleTime: 30_000,
    retry: 1,
  })

const StorageKeyInput = ({
  id,
  value = "",
  onChange,
  placeholder,
  extensions,
  foldersOnly,
  inputRef,
}: StorageKeyInputProps) => {
  const [open, setOpen] = useState(false)
  const [active, setActive] = useState(0)
  const localRef = useRef<HTMLInputElement | null>(null)

  const cut = value.lastIndexOf("/") + 1
  const dir = value.slice(0, cut)
  const tail = value.slice(cut).toLowerCase()
  const listing = useStorageListing(dir, open)

  const entries: Entry[] = listing.data
    ? [
        ...listing.data.folders.map((key) => ({
          key,
          name: key.slice(dir.length),
          folder: true,
        })),
        ...(foldersOnly ? [] : listing.data.files)
          .filter(
            (f) =>
              !extensions ||
              extensions.some((ext) => f.key.toLowerCase().endsWith(ext)),
          )
          .map((f) => ({ key: f.key, name: f.name, folder: false })),
      ].filter((e) => e.name.toLowerCase().includes(tail) && e.key !== value)
    : []
  const shown = entries.slice(0, 50)
  const showList = open

  function pick(entry: Entry) {
    onChange(entry.key)
    setActive(0)
    setOpen(entry.folder)
    requestAnimationFrame(() => localRef.current?.focus())
  }

  function onKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (!showList) return
    if (e.key === "Escape") {
      e.stopPropagation()
      setOpen(false)
      return
    }
    if (!shown.length) return
    if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      e.preventDefault()
      const step = e.key === "ArrowDown" ? 1 : -1
      setActive((active + step + shown.length) % shown.length)
    } else if (e.key === "Enter" || e.key === "Tab") {
      e.preventDefault()
      pick(shown[Math.min(active, shown.length - 1)])
    }
  }

  return (
    <Popover
      isOpen={showList}
      autoFocus={false}
      returnFocusOnClose={false}
      closeOnBlur={false}
      placement="bottom-start"
      matchWidth
      isLazy
    >
      <PopoverAnchor>
        <InputGroup>
          <Input
            id={id}
            ref={(el) => {
              localRef.current = el
              if (typeof inputRef === "function") inputRef(el)
            }}
            value={value}
            placeholder={placeholder}
            fontFamily="mono"
            fontSize="sm"
            autoComplete="off"
            spellCheck={false}
            onChange={(e) => {
              setActive(0)
              setOpen(true)
              onChange(e.target.value)
            }}
            onFocus={() => setOpen(true)}
            onClick={() => setOpen(true)}
            onKeyDown={onKeyDown}
            onBlur={() => setTimeout(() => setOpen(false), 150)}
            pr={value ? 8 : undefined}
          />
          {value && (
            <InputRightElement>
              <IconButton
                aria-label="Clear"
                icon={<FiX />}
                size="xs"
                variant="ghost"
                onClick={() => {
                  onChange("")
                  localRef.current?.focus()
                }}
              />
            </InputRightElement>
          )}
        </InputGroup>
      </PopoverAnchor>
      <Portal>
        <PopoverContent
          rootProps={{ zIndex: "tooltip" }}
          w="full"
          py={1}
          maxH="240px"
          overflowY="auto"
          _focus={{ boxShadow: "md" }}
        >
          {listing.isLoading ? (
            <HStack px={3} py={1}>
              <Spinner size="xs" />
              <Text fontSize="xs" color="gray.500">
                Loading {dir || "bucket root"}
              </Text>
            </HStack>
          ) : listing.isError ? (
            <Text px={3} py={1} fontSize="xs" color="red.500">
              Cannot list {dir || "bucket root"}: {listing.error.message}
            </Text>
          ) : !shown.length ? (
            <Text px={3} py={1} fontSize="xs" color="gray.500">
              No{" "}
              {foldersOnly
                ? "subfolders"
                : `${extensions?.join(", ") ?? ""} files`}
              {tail ? " matching" : ""} in {dir || "bucket root"}
            </Text>
          ) : (
            shown.map((entry, i) => (
              <HStack
                key={entry.key}
                px={3}
                py={1}
                cursor="pointer"
                fontFamily="mono"
                fontSize="sm"
                bg={i === active ? "gray.100" : undefined}
                _dark={{ bg: i === active ? "gray.600" : undefined }}
                onMouseEnter={() => setActive(i)}
                onMouseDown={(e) => {
                  e.preventDefault()
                  pick(entry)
                }}
              >
                <Box as={entry.folder ? FiFolder : FiFile} flexShrink={0} />
                <Text isTruncated>{entry.name}</Text>
              </HStack>
            ))
          )}
        </PopoverContent>
      </Portal>
    </Popover>
  )
}

export default StorageKeyInput
