import { Container } from "@chakra-ui/react"
import { createFileRoute, useNavigate } from "@tanstack/react-router"
import { z } from "zod"
import PageHeader from "../../components/Common/PageHeader"
import PipelinesTable from "../../components/Pipelines/PipelinesTable"

const pipelinesSearchSchema = z.object({
  page: z.number().catch(1),
})

export const Route = createFileRoute("/_layout/pipelines")({
  component: Pipelines,
  validateSearch: (search) => pipelinesSearchSchema.parse(search),
})

function Pipelines() {
  const { page } = Route.useSearch()
  const navigate = useNavigate({ from: Route.fullPath })
  const setPage = (page: number) =>
    navigate({ search: (prev) => ({ ...prev, page }) })
  return (
    <Container maxW="full">
      <PageHeader eyebrow="Processing" title="Pipelines" />
      <PipelinesTable page={page} onPageChange={setPage} />
    </Container>
  )
}
