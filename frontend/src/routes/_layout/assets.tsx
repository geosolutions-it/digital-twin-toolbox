import {
  Badge,
  Box,
  Button,
  Container,
  Flex,
  FormControl,
  FormLabel,
  Icon,
  Input,
  Modal,
  ModalBody,
  ModalCloseButton,
  ModalContent,
  ModalFooter,
  ModalHeader,
  ModalOverlay,
  SkeletonText,
  Table,
  TableContainer,
  Tbody,
  Td,
  Text,
  Th,
  Thead,
  Tr,
  useDisclosure,
} from "@chakra-ui/react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import React from "react"
import { type SubmitHandler, useForm } from "react-hook-form"
import { FiFile, FiFolder, FiPlay, FiPlus, FiUpload } from "react-icons/fi"
import { listStorage, uploadToStorage } from "../../api/storageBrowser"
import NewBatchModal from "../../components/Pipelines/NewBatchModal"
import PageHeader from "../../components/Common/PageHeader"
import useCustomToast from "../../hooks/useCustomToast"

export const Route = createFileRoute("/_layout/assets")({
  component: Assets,
})

function humanSize(bytes: number): string {
  if (!bytes) return "0 B"
  const units = ["B", "KB", "MB", "GB", "TB"]
  const i = Math.floor(Math.log(bytes) / Math.log(1024))
  return `${(bytes / 1024 ** i).toFixed(i === 0 ? 0 : 1)} ${units[i]}`
}

function extOf(name: string): string {
  const parts = name.split(".")
  return parts.length > 1 ? parts.pop()!.toLowerCase() : "file"
}

interface UploadProps {
  isOpen: boolean
  onClose: () => void
  initialPrefix: string
}

interface UploadFormValues {
  prefix: string
  file: FileList
}

const UploadModal = ({ isOpen, onClose, initialPrefix }: UploadProps) => {
  const queryClient = useQueryClient()
  const showToast = useCustomToast()
  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<UploadFormValues>({ mode: "onBlur" })

  React.useEffect(() => {
    if (isOpen) reset({ prefix: initialPrefix })
  }, [isOpen, initialPrefix, reset])

  const mutation = useMutation({
    mutationFn: (data: UploadFormValues) =>
      uploadToStorage(data.file[0], data.prefix || ""),
    onSuccess: (res) => {
      showToast("Uploaded", res.key, "success")
      reset()
      onClose()
    },
    onError: () => {
      showToast("An error occurred.", "Could not upload the file.", "error")
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["storage"] })
    },
  })

  const onSubmit: SubmitHandler<UploadFormValues> = (data) => mutation.mutate(data)

  return (
    <Modal isOpen={isOpen} onClose={onClose} size={{ base: "sm", md: "md" }} isCentered>
      <ModalOverlay />
      <ModalContent as="form" onSubmit={handleSubmit(onSubmit)}>
        <ModalHeader>Upload to bucket</ModalHeader>
        <ModalCloseButton />
        <ModalBody pb={6} display="flex" flexDirection="column" gap={4}>
          <FormControl>
            <FormLabel htmlFor="prefix">Destination folder</FormLabel>
            <Input id="prefix" placeholder="e.g. city-timisoara/" {...register("prefix")} />
          </FormControl>
          <FormControl isRequired isInvalid={!!errors.file}>
            <FormLabel htmlFor="file">File</FormLabel>
            <Input
              id="file"
              {...register("file", { required: "File is required." })}
              disabled={mutation.isPending}
              type="file"
              p={0}
              sx={{
                "::file-selector-button": {
                  height: 10,
                  padding: 0,
                  mr: 2,
                  pr: 2,
                  pl: 2,
                  border: "none",
                  fontWeight: "normal",
                  cursor: "pointer",
                },
              }}
            />
          </FormControl>
        </ModalBody>
        <ModalFooter gap={3}>
          <Button variant="primary" type="submit" isLoading={isSubmitting || mutation.isPending}>
            Upload
          </Button>
          <Button onClick={onClose}>Cancel</Button>
        </ModalFooter>
      </ModalContent>
    </Modal>
  )
}

function Breadcrumbs({ cwd, onNavigate }: { cwd: string; onNavigate: (p: string) => void }) {
  const segs = cwd ? cwd.replace(/\/$/, "").split("/") : []
  let acc = ""
  return (
    <Flex align="center" gap={1} fontSize="sm" flexWrap="wrap">
      <Box as="button" type="button" color="blue.500" fontWeight="semibold" onClick={() => onNavigate("")}>
        root
      </Box>
      {segs.map((seg) => {
        acc = acc ? `${acc}/${seg}` : seg
        const target = `${acc}/`
        return (
          <Flex key={target} align="center" gap={1}>
            <Text color="gray.400">/</Text>
            <Box as="button" type="button" color="blue.500" fontWeight="semibold" onClick={() => onNavigate(target)}>
              {seg}
            </Box>
          </Flex>
        )
      })}
    </Flex>
  )
}

const POINTCLOUD_EXT = [".laz", ".las"]
const VECTOR_EXT = [".fgb", ".gpkg", ".geojson", ".zip"]
const TERRAIN_EXT = [".tif", ".tiff", ".vrt"]

function hintTypeForFile(
  name: string,
): "PointCloud" | "Polygon" | "Terrain" | undefined {
  const n = name.toLowerCase()
  if (POINTCLOUD_EXT.some((e) => n.endsWith(e))) return "PointCloud"
  if (VECTOR_EXT.some((e) => n.endsWith(e))) return "Polygon"
  if (TERRAIN_EXT.some((e) => n.endsWith(e))) return "Terrain"
  return undefined
}

function BucketBrowser({ cwd, setCwd }: { cwd: string; setCwd: (p: string) => void }) {
  const [batchPrefix, setBatchPrefix] = React.useState("")
  const [processKey, setProcessKey] = React.useState("")
  const [processType, setProcessType] = React.useState<"PointCloud" | "Polygon" | "Terrain" | undefined>()
  const batchModal = useDisclosure()
  const processModal = useDisclosure()

  const { data, isPending } = useQuery({
    queryKey: ["storage", cwd],
    queryFn: () => listStorage(cwd),
  })

  const openBatch = (prefix: string) => {
    setBatchPrefix(prefix)
    batchModal.onOpen()
  }

  const openProcess = (key: string, type?: "PointCloud" | "Polygon" | "Terrain") => {
    setProcessKey(key)
    setProcessType(type)
    processModal.onOpen()
  }

  const folders = data?.folders ?? []
  const files = data?.files ?? []
  const empty = !isPending && folders.length === 0 && files.length === 0

  return (
    <>
      <Flex align="center" gap={3} pb={4} flexWrap="wrap">
        <Badge variant="outline" fontFamily="mono" textTransform="none" px={2} py={1} borderRadius="md">
          s3://bucket
        </Badge>
        <Breadcrumbs cwd={cwd} onNavigate={setCwd} />
      </Flex>

      <TableContainer borderWidth="1px" borderRadius="md">
        <Table size="sm">
          <Thead>
            <Tr>
              <Th>Name</Th>
              <Th>Type</Th>
              <Th isNumeric>Size</Th>
              <Th />
            </Tr>
          </Thead>
          <Tbody>
            {isPending ? (
              <Tr>
                {new Array(4).fill(null).map((_, i) => (
                  <Td key={i}>
                    <SkeletonText noOfLines={1} paddingBlock="12px" />
                  </Td>
                ))}
              </Tr>
            ) : (
              <>
                {folders.map((folder) => {
                  const name = folder.slice(cwd.length).replace(/\/$/, "")
                  return (
                    <Tr key={folder} _hover={{ bg: "blackAlpha.50", _dark: { bg: "whiteAlpha.100" } }}>
                      <Td>
                        <Flex
                          as="button"
                          type="button"
                          align="center"
                          gap={2}
                          onClick={() => setCwd(folder)}
                          fontWeight="medium"
                        >
                          <Icon as={FiFolder} color="blue.400" />
                          {name}/
                        </Flex>
                      </Td>
                      <Td>
                        <Badge colorScheme="blue">folder</Badge>
                      </Td>
                      <Td isNumeric color="gray.500">
                        —
                      </Td>
                      <Td textAlign="right">
                        <Button size="xs" variant="ghost" leftIcon={<FiPlus />} onClick={() => openBatch(folder)}>
                          Batch
                        </Button>
                      </Td>
                    </Tr>
                  )
                })}
                {files.map((file) => {
                  const hintType = hintTypeForFile(file.name)
                  return (
                    <Tr key={file.key} _hover={{ bg: "blackAlpha.50", _dark: { bg: "whiteAlpha.100" } }}>
                      <Td>
                        <Flex align="center" gap={2} fontFamily="mono" fontSize="xs">
                          <Icon as={FiFile} color="gray.400" />
                          {file.name}
                        </Flex>
                      </Td>
                      <Td>
                        <Badge>{extOf(file.name)}</Badge>
                      </Td>
                      <Td isNumeric color="gray.500">
                        {humanSize(file.size)}
                      </Td>
                      <Td textAlign="right">
                        {hintType && (
                          <Button
                            size="xs"
                            variant="ghost"
                            leftIcon={<FiPlay />}
                            onClick={() => openProcess(file.key, hintType)}
                          >
                            Process
                          </Button>
                        )}
                      </Td>
                    </Tr>
                  )
                })}
                {empty && (
                  <Tr>
                    <Td colSpan={4}>
                      <Text textAlign="center" color="gray.500" py={8}>
                        Empty prefix.
                      </Text>
                    </Td>
                  </Tr>
                )}
              </>
            )}
          </Tbody>
        </Table>
      </TableContainer>

      <Text fontSize="xs" color="gray.500" mt={3}>
        Listing the bucket by prefix. Use <b>Batch</b> on a folder to process every
        supported file under it (point clouds, vectors, zipped shapefiles); the
        workflow is detected per file. No per-file registration needed.
      </Text>

      <NewBatchModal
        isOpen={batchModal.isOpen}
        onClose={batchModal.onClose}
        initialPrefix={batchPrefix}
        selectableType
      />
      <NewBatchModal
        isOpen={processModal.isOpen}
        onClose={processModal.onClose}
        fileKey={processKey}
        pipelineType={processType}
      />
    </>
  )
}

function Assets() {
  const [cwd, setCwd] = React.useState("")
  const uploadModal = useDisclosure()
  return (
    <Container maxW="full">
      <PageHeader
        eyebrow="Bucket storage"
        title="Assets"
        actions={
          <Button
            gap={1}
            onClick={uploadModal.onOpen}
            variant="outline"
            size="sm"
            leftIcon={<FiUpload />}
          >
            Upload
          </Button>
        }
      />
      <UploadModal isOpen={uploadModal.isOpen} onClose={uploadModal.onClose} initialPrefix={cwd} />
      <BucketBrowser cwd={cwd} setCwd={setCwd} />
    </Container>
  )
}
