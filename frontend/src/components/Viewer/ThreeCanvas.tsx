import React from "react"
import * as THREE from "three"
import { MapControls } from "three/examples/jsm/controls/MapControls.js"

const setDefaultCameraLocation = (camera: any, controls: any) => {
  camera.position.set(0, 3000, 0)
  controls.target.set(0, 0, 0)
}

const material = new THREE.MeshNormalMaterial()
const pointMaterial = new THREE.PointsMaterial({ size: 4, vertexColors: true })

interface ThreeCanvasProps {
  onMount: (options: any) => any
}

function ThreeCanvas({ onMount }: ThreeCanvasProps) {
  const canvas = React.useRef(null)
  const options = React.useRef({})
  React.useEffect(() => {
    const canvasNode = canvas?.current || { clientWidth: 0, clientHeight: 0 }

    const scene = new THREE.Scene()
    const camera = new THREE.PerspectiveCamera(
      75,
      canvasNode.clientWidth / canvasNode.clientHeight,
      0.1,
      1000000000,
    )

    const renderer = new THREE.WebGLRenderer({
      canvas: canvas?.current || undefined,
    })
    renderer.setSize(canvasNode.clientWidth, canvasNode.clientHeight)

    const controls = new MapControls(camera, renderer.domElement)
    controls.enableDamping = false
    controls.dampingFactor = 0.05

    setDefaultCameraLocation(camera, controls)

    const axesHelper = new THREE.AxesHelper(500)
    scene.add(axesHelper)

    const gridGround = new THREE.GridHelper(3000, 150, 0x3f3f3f, 0x3f3f3f)
    scene.add(gridGround)
    let removed = false
    let requestAnimation: any
    function animate() {
      if (!removed) {
        requestAnimation = requestAnimationFrame(animate)
        controls.update()
        renderer.render(scene, camera)
      }
    }
    animate()
    const group = new THREE.Group()
    scene.add(group)
    options.current = { group, material, pointMaterial }
    window.addEventListener("resize", onWindowResize, false)
    function onWindowResize() {
      camera.aspect = canvasNode.clientWidth / canvasNode.clientHeight
      camera.updateProjectionMatrix()
      renderer.setSize(canvasNode.clientWidth, canvasNode.clientHeight)
    }
    return () => {
      removed = true
      if (requestAnimation) {
        cancelAnimationFrame(requestAnimation)
      }
      for (let i = 0; i < group.children.length; i++) {
        const mesh: any = group.children[i]
        mesh.geometry.dispose()
      }
      group.children.forEach((child: any) => group.remove(child))
      group.children = []
      renderer.dispose()
    }
  }, [])

  const _onMount = React.useRef(() => {});
  _onMount.current = () => onMount(options.current);
  React.useEffect(() => {
    _onMount.current();
  }, [])
  return (
    <canvas
      ref={canvas}
      style={{ position: "absolute", width: "100%", height: "100%" }}
    />
  )
}

export default ThreeCanvas
