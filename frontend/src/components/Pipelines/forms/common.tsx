import {
  Checkbox,
  FormControl,
  FormErrorMessage,
  FormLabel,
  Input,
  Select,
  Text,
} from "@chakra-ui/react"
import type { ReactElement, ReactNode } from "react"
import {
  Controller,
  type FieldValues,
  type Path,
  useFormContext,
  useWatch,
} from "react-hook-form"
import type {
  AnyPipelineConfig,
  HeightReference,
  SampleFeature,
} from "../../../api/types"
import ExpressionInput, { isInvalidExpression } from "../ExpressionInput"
import StorageKeyInput from "../StorageKeyInput"

export const RASTER_EXTENSIONS = [".tif", ".tiff", ".jp2"]

export interface FieldsProps {
  fieldNames?: string[]
  sampleFeatures?: SampleFeature[]
}

export interface PipelineForm<V extends FieldValues, C> {
  defaults: V
  toConfig: (values: V) => Partial<C>
  fromConfig: (config: AnyPipelineConfig) => V
  Fields: (props: FieldsProps) => ReactElement
}

export const numText = (v: unknown) => (typeof v === "number" ? String(v) : "")

export const exprText = (v: unknown) =>
  Array.isArray(v) ? v : typeof v === "number" ? String(v) : ""

/** An expression input's value as sent: a number, a formula array, or nothing. */
export function exprValue(v: unknown): number | unknown[] | undefined {
  if (v == null || v === "") return undefined
  if (Array.isArray(v)) return v
  const n = Number(v)
  return Number.isNaN(n) ? undefined : n
}

function Help({ children }: { children?: ReactNode }) {
  if (!children) return null
  return (
    <Text fontSize="xs" color="gray.500" mt={1}>
      {children}
    </Text>
  )
}

function useError(name: string) {
  const {
    formState: { errors },
  } = useFormContext()
  return errors[name]?.message as string | undefined
}

interface NumberFieldProps {
  name: string
  label: ReactNode
  placeholder?: string
  step?: string
  required?: string
  help?: ReactNode
}

function NumberField({
  name,
  label,
  placeholder,
  step,
  required,
  help,
}: NumberFieldProps) {
  const { register } = useFormContext()
  const error = useError(name)
  return (
    <FormControl isRequired={!!required} isInvalid={!!error}>
      <FormLabel htmlFor={name}>{label}</FormLabel>
      <Input
        id={name}
        type="number"
        step={step}
        placeholder={placeholder}
        {...register(name, required ? { required } : undefined)}
      />
      {error && <FormErrorMessage>{error}</FormErrorMessage>}
      <Help>{help}</Help>
    </FormControl>
  )
}

interface CheckboxFieldProps {
  name: string
  label: ReactNode
  help?: ReactNode
}

function CheckboxField({ name, label, help }: CheckboxFieldProps) {
  const { register } = useFormContext()
  return (
    <FormControl>
      <Checkbox {...register(name)}>{label}</Checkbox>
      <Help>{help}</Help>
    </FormControl>
  )
}

interface SelectFieldProps {
  name: string
  label: ReactNode
  children: ReactNode
}

function SelectField({ name, label, children }: SelectFieldProps) {
  const { register } = useFormContext()
  return (
    <FormControl>
      <FormLabel htmlFor={name}>{label}</FormLabel>
      <Select id={name} {...register(name)}>
        {children}
      </Select>
    </FormControl>
  )
}

interface StorageKeyFieldProps {
  name: string
  label: ReactNode
  placeholder?: string
  extensions?: string[]
  foldersOnly?: boolean
  required?: string
  help?: ReactNode
}

function StorageKeyField({
  name,
  label,
  placeholder,
  extensions,
  foldersOnly,
  required,
  help,
}: StorageKeyFieldProps) {
  const { control } = useFormContext()
  const error = useError(name)
  return (
    <FormControl isRequired={!!required} isInvalid={!!error}>
      <FormLabel htmlFor={name}>{label}</FormLabel>
      <Controller
        control={control}
        name={name}
        rules={required ? { required } : undefined}
        render={({ field }) => (
          <StorageKeyInput
            id={name}
            value={field.value}
            onChange={field.onChange}
            inputRef={field.ref}
            placeholder={placeholder}
            extensions={extensions}
            foldersOnly={foldersOnly}
          />
        )}
      />
      {error && <FormErrorMessage>{error}</FormErrorMessage>}
      <Help>{help}</Help>
    </FormControl>
  )
}

interface ExpressionFieldProps extends FieldsProps {
  name: string
  label: ReactNode
  type: "number" | "string"
  placeholder?: string
  literals?: string[]
}

function ExpressionField({
  name,
  label,
  type,
  placeholder,
  literals,
  fieldNames,
  sampleFeatures,
}: ExpressionFieldProps) {
  const { control } = useFormContext()
  return (
    <FormControl>
      <FormLabel>{label}</FormLabel>
      <Controller
        control={control}
        name={name}
        rules={{
          validate: (v) => !isInvalidExpression(v) || "Fix the formula",
        }}
        render={({ field }) => (
          <ExpressionInput
            id={name}
            type={type}
            value={field.value}
            onChange={field.onChange}
            inputRef={field.ref}
            fields={fieldNames}
            features={sampleFeatures}
            literals={literals}
            placeholder={placeholder}
          />
        )}
      />
    </FormControl>
  )
}

type Named<V extends FieldValues, P> = Omit<P, "name"> & { name: Path<V> }

/** The field components with `name` checked against one form's values. */
export function fieldsFor<V extends FieldValues>() {
  return {
    Number: NumberField as (p: Named<V, NumberFieldProps>) => ReactElement,
    Checkbox: CheckboxField as (
      p: Named<V, CheckboxFieldProps>,
    ) => ReactElement,
    Select: SelectField as (p: Named<V, SelectFieldProps>) => ReactElement,
    StorageKey: StorageKeyField as (
      p: Named<V, StorageKeyFieldProps>,
    ) => ReactElement,
    Expression: ExpressionField as (
      p: Named<V, ExpressionFieldProps>,
    ) => ReactElement,
  }
}

export interface HeightValues {
  height_reference: HeightReference
  vertical_epsg: string
}

export const heightDefaults: HeightValues = {
  height_reference: "source",
  vertical_epsg: "",
}

export function heightToConfig(v: HeightValues) {
  const data: { height_reference?: HeightReference; vertical_epsg?: number } =
    {}
  if (v.height_reference && v.height_reference !== "source") {
    data.height_reference = v.height_reference
    if (v.vertical_epsg) data.vertical_epsg = Number(v.vertical_epsg)
  }
  return data
}

export const heightFromConfig = (c: AnyPipelineConfig): HeightValues => ({
  height_reference: c.height_reference || "source",
  vertical_epsg: numText(c.vertical_epsg),
})

const GEOID_HELP: Record<HeightReference, string> = {
  source: "",
  ellipsoidal: "Geoid of the source heights, EGM2008 when empty.",
  orthometric: "Geoid of the output heights, EGM2008 when empty.",
}

export function HeightFields() {
  const reference = useWatch<HeightValues, "height_reference">({
    name: "height_reference",
  })
  return (
    <>
      <SelectField name="height_reference" label="Height conversion">
        <option value="source">None</option>
        <option value="ellipsoidal">Geoid → Ellipsoidal</option>
        <option value="orthometric">Ellipsoidal → Geoid</option>
      </SelectField>
      {reference && reference !== "source" && (
        <NumberField
          name="vertical_epsg"
          label="Geoid EPSG (optional)"
          placeholder="3855"
          help={GEOID_HELP[reference]}
        />
      )}
    </>
  )
}
