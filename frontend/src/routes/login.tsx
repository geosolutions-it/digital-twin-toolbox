import { ViewIcon, ViewOffIcon } from "@chakra-ui/icons"
import {
  Button,
  Container,
  Flex,
  FormControl,
  FormErrorMessage,
  Icon,
  Image,
  Input,
  InputGroup,
  InputRightElement,
  Link,
  Text,
  useBoolean,
} from "@chakra-ui/react"
import {
  Link as RouterLink,
  createFileRoute,
  redirect,
} from "@tanstack/react-router"
import { type SubmitHandler, useForm } from "react-hook-form"

import Logo from "/assets/images/logo.svg"
import type { Body_login_login_access_token as AccessToken } from "../client"
import useAuth, { isLoggedIn } from "../hooks/useAuth"
import { emailPattern } from "../utils"

export const Route = createFileRoute("/login")({
  component: Login,
  beforeLoad: async () => {
    if (isLoggedIn()) {
      throw redirect({
        to: "/",
      })
    }
  },
})

function Login() {
  const [show, setShow] = useBoolean()
  const { loginMutation, error, resetError } = useAuth()
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<AccessToken>({
    mode: "onBlur",
    criteriaMode: "all",
    defaultValues: {
      username: "",
      password: "",
    },
  })

  const onSubmit: SubmitHandler<AccessToken> = async (data) => {
    if (isSubmitting) return

    resetError()

    try {
      await loginMutation.mutateAsync(data)
    } catch {
      // error is handled by useAuth hook
    }
  }

  return (
    <>
      <Container
        h="calc(var(--dtt-vh))"
        justifyContent="center"
        centerContent
      >
        <Container
          as="form"
          onSubmit={handleSubmit(onSubmit)}
          alignItems="stretch"
          gap={4}
          maxW="sm"
          centerContent
        >
          <Flex alignItems="center" justifyContent="center" mb={4}>
            <Image
              src={Logo}
              alt="Digital Twin Toolbox logo"
              height="48px"
              maxW="2xs"
              alignSelf="center"
              mr={2}
            />
            <Text as="h1" fontSize="30px">
              Digital Twin Toolbox
            </Text>
          </Flex>
          <FormControl id="username" isInvalid={!!errors.username || !!error}>
            <Input
              id="username"
              {...register("username", {
                required: "Username is required",
                pattern: emailPattern,
              })}
              placeholder="Email"
              type="email"
              required
            />
            {errors.username && (
              <FormErrorMessage>{errors.username.message}</FormErrorMessage>
            )}
          </FormControl>
          <FormControl id="password" isInvalid={!!error}>
            <InputGroup>
              <Input
                {...register("password", {
                  required: "Password is required",
                })}
                type={show ? "text" : "password"}
                placeholder="Password"
                required
              />
              <InputRightElement
                color="ui.dim"
                _hover={{
                  cursor: "pointer",
                }}
              >
                <Icon
                  as={show ? ViewOffIcon : ViewIcon}
                  onClick={setShow.toggle}
                  aria-label={show ? "Hide password" : "Show password"}
                >
                  {show ? <ViewOffIcon /> : <ViewIcon />}
                </Icon>
              </InputRightElement>
            </InputGroup>
            {error && <FormErrorMessage>{error}</FormErrorMessage>}
          </FormControl>
          <Link as={RouterLink} to="/recover-password" color="blue.500">
            Forgot password?
          </Link>
          <Button variant="primary" type="submit" isLoading={isSubmitting}>
            Log In
          </Button>
          <Text>
            Don't have an account?{" "}
            <Link as={RouterLink} to="/signup" color="blue.500">
              Sign up
            </Link>
          </Text>
        </Container>
      </Container>
    </>
  )
}
