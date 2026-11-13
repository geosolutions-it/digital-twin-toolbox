import { Button, Container, useDisclosure } from "@chakra-ui/react"
import { createFileRoute } from "@tanstack/react-router"
import React from "react"
import { FiUpload } from "react-icons/fi"
import BucketBrowser from "../../components/Assets/BucketBrowser"
import UploadModal from "../../components/Assets/UploadModal"
import PageHeader from "../../components/Common/PageHeader"

export const Route = createFileRoute("/_layout/assets")({
  component: Assets,
})

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
      <UploadModal
        isOpen={uploadModal.isOpen}
        onClose={uploadModal.onClose}
        initialPrefix={cwd}
      />
      <BucketBrowser cwd={cwd} setCwd={setCwd} />
    </Container>
  )
}
