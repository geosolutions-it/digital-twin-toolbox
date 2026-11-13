import {
  Badge,
  Box,
  Button,
  Flex,
  Icon,
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
import { useQuery } from "@tanstack/react-query"
import React from "react"
import { FiFile, FiFolder, FiPlay, FiPlus } from "react-icons/fi"
import { listStorage } from "../../api/storageBrowser"
import type { PipelineType } from "../../api/types"
import PipelineModal from "../Pipelines/PipelineModal"

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

function Breadcrumbs({
  cwd,
  onNavigate,
}: { cwd: string; onNavigate: (p: string) => void }) {
  const segs = cwd ? cwd.replace(/\/$/, "").split("/") : []
  let acc = ""
  return (
    <Flex align="center" gap={1} fontSize="sm" flexWrap="wrap">
      <Box
        as="button"
        type="button"
        color="blue.500"
        fontWeight="semibold"
        onClick={() => onNavigate("")}
      >
        root
      </Box>
      {segs.map((seg) => {
        acc = acc ? `${acc}/${seg}` : seg
        const target = `${acc}/`
        return (
          <Flex key={target} align="center" gap={1}>
            <Text color="gray.400">/</Text>
            <Box
              as="button"
              type="button"
              color="blue.500"
              fontWeight="semibold"
              onClick={() => onNavigate(target)}
            >
              {seg}
            </Box>
          </Flex>
        )
      })}
    </Flex>
  )
}

export default function BucketBrowser({
  cwd,
  setCwd,
}: { cwd: string; setCwd: (p: string) => void }) {
  const [batchPrefix, setBatchPrefix] = React.useState("")
  const [processKey, setProcessKey] = React.useState("")
  const [processType, setProcessType] = React.useState<
    PipelineType | undefined
  >()
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

  const openProcess = (key: string, type?: PipelineType) => {
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
        <Badge
          variant="outline"
          fontFamily="mono"
          textTransform="none"
          px={2}
          py={1}
          borderRadius="md"
        >
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
                    <Tr
                      key={folder}
                      _hover={{
                        bg: "blackAlpha.50",
                        _dark: { bg: "whiteAlpha.100" },
                      }}
                    >
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
                        <Button
                          size="xs"
                          variant="ghost"
                          leftIcon={<FiPlus />}
                          onClick={() => openBatch(folder)}
                        >
                          Batch
                        </Button>
                      </Td>
                    </Tr>
                  )
                })}
                {files.map((file) => {
                  const hintType = file.pipeline ?? undefined
                  return (
                    <Tr
                      key={file.key}
                      _hover={{
                        bg: "blackAlpha.50",
                        _dark: { bg: "whiteAlpha.100" },
                      }}
                    >
                      <Td>
                        <Flex
                          align="center"
                          gap={2}
                          fontFamily="mono"
                          fontSize="xs"
                        >
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
        Listing the bucket by prefix. Use <b>Batch</b> on a folder to run the
        picked workflow on every matching file under it (point clouds, vectors,
        zipped shapefiles, elevation rasters, zipped meshes, city models in
        CityGML or CityJSON); files of other types are skipped. No per-file
        registration needed.
      </Text>

      <PipelineModal
        isOpen={batchModal.isOpen}
        onClose={batchModal.onClose}
        initialPrefix={batchPrefix}
        selectableType
      />
      <PipelineModal
        isOpen={processModal.isOpen}
        onClose={processModal.onClose}
        fileKey={processKey}
        pipelineType={processType}
      />
    </>
  )
}
