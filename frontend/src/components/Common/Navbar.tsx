import type { ComponentType, ElementType } from "react"

import { Button, Flex, Icon, useDisclosure } from "@chakra-ui/react"
import { FaPlus } from "react-icons/fa"

interface NavbarProps {
  type: string
  addModalAs: ComponentType | ElementType
}

const Navbar = ({ type, addModalAs }: NavbarProps) => {
  const addModal = useDisclosure()

  const AddModal = addModalAs
  return (
    <>
      <Flex py={8} gap={4}>
        <Button variant="outline" gap={1} size="sm" onClick={addModal.onOpen}>
          <Icon as={FaPlus} /> Add {type}
        </Button>
        <AddModal isOpen={addModal.isOpen} onClose={addModal.onClose} />
      </Flex>
    </>
  )
}

export default Navbar
