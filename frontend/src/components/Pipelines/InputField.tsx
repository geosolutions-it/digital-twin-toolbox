import {
  Flex,
  FormControl,
  FormErrorMessage,
  FormHelperText,
  FormLabel,
  IconButton,
  Input,
  Tooltip,
} from "@chakra-ui/react"
import { useState } from "react"
import { FiEdit2, FiX } from "react-icons/fi"
import StorageKeyInput from "./StorageKeyInput"

interface InputFieldProps {
  label: string
  /** the stored input; also what ✕ restores */
  value: string
  /** without onChange the field is display only */
  onChange?: (value: string) => void
  current?: string
  folder?: boolean
  error?: string
}

/** A pipeline's input file or folder: read-only, with a pencil to re-point it when editing. */
export default function InputField({
  label,
  value,
  onChange,
  current,
  folder,
  error,
}: InputFieldProps) {
  const [editing, setEditing] = useState(false)
  const shown = current ?? value

  return (
    <FormControl isInvalid={!!error}>
      <FormLabel htmlFor="pipeline-input">{label}</FormLabel>
      <Flex gap={2} align="center">
        {editing && onChange ? (
          <StorageKeyInput
            id="pipeline-input"
            value={shown}
            onChange={onChange}
            foldersOnly={folder}
            placeholder={folder ? "e.g. lidar/" : "e.g. lidar/tile.laz"}
          />
        ) : (
          <Input
            id="pipeline-input"
            value={shown}
            isReadOnly
            fontFamily="mono"
            fontSize="sm"
            bg="blackAlpha.50"
            color="gray.500"
            _dark={{ bg: "whiteAlpha.100", color: "gray.400" }}
            cursor="default"
            _focusVisible={{ borderColor: "inherit" }}
          />
        )}
        {onChange &&
          (editing ? (
            <Tooltip label="Keep the current input">
              <IconButton
                aria-label="Keep the current input"
                icon={<FiX />}
                size="sm"
                variant="ghost"
                onClick={() => {
                  onChange(value)
                  setEditing(false)
                }}
              />
            </Tooltip>
          ) : (
            <Tooltip label={folder ? "Change the folder" : "Change the file"}>
              <IconButton
                aria-label={folder ? "Change the folder" : "Change the file"}
                icon={<FiEdit2 />}
                size="sm"
                variant="ghost"
                onClick={() => setEditing(true)}
              />
            </Tooltip>
          ))}
      </Flex>
      {error ? (
        <FormErrorMessage>{error}</FormErrorMessage>
      ) : (
        editing &&
        shown !== value && (
          <FormHelperText fontSize="xs">
            The output folder stays the same. Use Save & run to rebuild from the
            new input.
          </FormHelperText>
        )
      )}
    </FormControl>
  )
}
