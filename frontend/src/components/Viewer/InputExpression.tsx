import {
  Box,
  Button,
  HStack,
  IconButton,
  Input,
  Menu,
  MenuButton,
  MenuItem,
  MenuList,
  Select,
} from "@chakra-ui/react"
import React from "react"
import { BsThreeDotsVertical } from "react-icons/bs"
import { FiTrash } from "react-icons/fi"

const operators: any = {
  concat: "+",
  property: "var",
}

interface ResizableInputMenuProps {
  type: string
  value: any
  onChange: (value: any) => any
}

const ResizableInputMenu = ({
  type,
  value,
  onChange,
}: ResizableInputMenuProps) => {
  return (
    <Menu>
      <MenuButton
        as={IconButton}
        icon={<BsThreeDotsVertical />}
        size="xs"
        margin={0}
        minW="1"
        borderRadius="none"
        variant="unstyled"
      />
      <MenuList>
        {type === "number" && (
          <>
            <MenuItem onClick={() => onChange(["+", value, 0])}>
              + Addition
            </MenuItem>
            <MenuItem onClick={() => onChange(["-", value, 0])}>
              - Subtraction
            </MenuItem>
            <MenuItem onClick={() => onChange(["*", value, 0])}>
              * Multiplication
            </MenuItem>
            <MenuItem onClick={() => onChange(["/", value, 0])}>
              / Division
            </MenuItem>
          </>
        )}
        {type === "text" && (
          <>
            <MenuItem onClick={() => onChange(["concat", value, ""])}>
              + Concat
            </MenuItem>
            <MenuItem onClick={() => onChange(["lowercase", value])}>
              a Lower case
            </MenuItem>
            <MenuItem onClick={() => onChange(["uppercase", value])}>
              A Upper case
            </MenuItem>
          </>
        )}
        <MenuItem onClick={() => onChange(["property", value])}>
          p Property
        </MenuItem>
        <MenuItem onClick={() => onChange(["func", value])}>
          f Function
        </MenuItem>
      </MenuList>
    </Menu>
  )
}

interface ResizableInputProps {
  type: string
  value: any
  onChange: (value: any) => any
}

function ResizableInput({ type, value, onChange }: ResizableInputProps) {
  const [width, setWidth] = React.useState("")
  function handleChange(event: any) {
    onChange(event.target.value)
  }
  React.useLayoutEffect(() => {
    setWidth(`${(value || "").length + 1}ch`)
  }, [value])
  return (
    <HStack
      gap={0}
      display="inline-flex"
      borderRadius="md"
      borderBottom="1px"
      borderBottomColor="gray.200"
    >
      <Input
        autoComplete="off"
        border="none"
        type={type}
        minW="2ch"
        textAlign="center"
        size="xs"
        bg="white"
        color="black"
        m={0}
        p={0}
        w={width}
        defaultValue={value}
        onChange={handleChange}
      />
      <ResizableInputMenu type={type} value={value} onChange={onChange} />
    </HStack>
  )
}

interface ResizableSelectProps {
  properties: any
  value: any
  onChange: (value: any) => any
}

function ResizableSelect({
  value,
  onChange,
  properties,
}: ResizableSelectProps) {
  const [width, setWidth] = React.useState("")
  function handleChange(event: any) {
    onChange(event.target.value)
  }
  React.useLayoutEffect(() => {
    setWidth(`${(value || "").length + 7}ch`)
  }, [value])
  return (
    <Select
      display="inline-block"
      border="none"
      fontFamily="monospace"
      w={width}
      maxW="100%"
      minW="2ch"
      size="xs"
      bg="white"
      color="black"
      m={0}
      value={value}
      onChange={handleChange}
    >
      <option value="" />
      {properties.map((property: any) => (
        <option key={property[0]} value={property[0]}>
          {property[0]}
        </option>
      ))}
    </Select>
  )
}

interface RecursiveInputProps {
  type: string
  properties: any
  value: any
  onChange: (value: any) => any
}

function RecursiveInput({
  type,
  value,
  onChange,
  properties,
}: RecursiveInputProps) {
  if (!Array.isArray(value) || !value) {
    return (
      <ResizableInput
        type={type}
        value={value}
        onChange={(newValue: any) => onChange(newValue)}
      />
    )
  }
  const [operator, ...args] = value
  const operatorLabel: string = operators[operator] || operator || ""

  if (["+", "-", "*", "/", "concat"].includes(operator)) {
    const [a, b] = args || []
    return (
      <Box display="inline-block" p={0.5} borderRadius="md" fontSize="xs">
        {" ( "}
        <RecursiveInput
          properties={properties}
          type={type}
          value={a}
          onChange={(newValue: any) => onChange([operator, newValue, b])}
        />
        <strong>{` ${operatorLabel} `}</strong>
        <RecursiveInput
          properties={properties}
          type={type}
          value={b}
          onChange={(newValue: any) => onChange([operator, a, newValue])}
        />{" "}
        <Button
          size="xs"
          minW="1"
          p={0}
          variant="unstyled"
          color="ui.danger"
          onClick={() => onChange(a)}
        >
          <FiTrash />
        </Button>
        {" ) "}
      </Box>
    )
  }
  if (["uppercase", "lowercase"].includes(operator)) {
    const [a] = args || []
    return (
      <Box display="inline-block" p={0.5} borderRadius="md" fontSize="xs">
        {` ${operatorLabel}(`}
        <RecursiveInput
          properties={properties}
          type={type}
          value={a}
          onChange={(newValue: any) => onChange([operator, newValue])}
        />
        <Button
          size="xs"
          minW="1"
          p={0}
          variant="unstyled"
          color="ui.danger"
          onClick={() => onChange(a)}
        >
          <FiTrash />
        </Button>
        {" ) "}
      </Box>
    )
  }
  if (["property"].includes(operator)) {
    const [a] = args || []
    return (
      <Box display="inline-block" p={0.5} borderRadius="md" fontSize="xs">
        {` ${operatorLabel}(`}
        <ResizableSelect
          properties={properties}
          value={a}
          onChange={(newValue: any) => onChange(["property", newValue])}
        />
        <Button
          size="xs"
          minW="1"
          p={0}
          variant="unstyled"
          color="ui.danger"
          onClick={() => onChange(undefined)}
        >
          <FiTrash />
        </Button>
        {" ) "}
      </Box>
    )
  }
  if (["func"].includes(operator)) {
    const [a] = args || []
    return (
      <Box display="inline-block" p={0.5} borderRadius="md" fontSize="xs">
        {` ${operatorLabel}(`}
        <ResizableSelect
          properties={[["$minZ"], ["$maxZ"]]}
          value={a}
          onChange={(newValue: any) => onChange(["func", newValue])}
        />
        <Button
          size="xs"
          minW="1"
          p={0}
          variant="unstyled"
          color="ui.danger"
          onClick={() => onChange(undefined)}
        >
          <FiTrash />
        </Button>
        {" ) "}
      </Box>
    )
  }
  return null
}

interface InputExpressionProps {
  id: string
  type: string
  properties: any
  value: any | undefined
  onChange: (value: any) => any
  defaultInput?: any | undefined
}

function InputExpression({
  id,
  type = "text",
  properties,
  value,
  onChange,
  defaultInput,
}: InputExpressionProps) {
  const propertiesList = Object.entries(properties)
  return Array.isArray(value) ? (
    <RecursiveInput
      type={type}
      value={value}
      properties={propertiesList}
      onChange={(newValue: any) => onChange(newValue)}
    />
  ) : (
    <HStack gap={0}>
      {defaultInput || (
        <Input
          id={id}
          autoComplete="off"
          size="xs"
          type={type}
          defaultValue={value}
          onChange={(event) => onChange(event.target.value)}
        />
      )}
      <ResizableInputMenu type={type} value={value} onChange={onChange} />
    </HStack>
  )
}

export default InputExpression
