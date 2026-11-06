import * as Cesium from "cesium"
import "cesium/Source/Widgets/widgets.css"
import { getPublicBasePath } from "../utils"

// filled by scripts/copy-cesium-assets.mjs; absolute because routes nest
window.CESIUM_BASE_URL = `${getPublicBasePath().replace(/\/?$/, "/")}cesium/`

declare global {
  interface Window {
    CESIUM_BASE_URL?: string
  }
}

// no ion assets are used; the OSM credit must stay
const hideIonLogo = document.createElement("style")
hideIonLogo.textContent = ".cesium-credit-logoContainer{display:none!important}"
document.head.appendChild(hideIonLogo)

const WMS_URL = "https://maps1.geosolutionsgroup.com/geoserver/wms"
const OSM_CREDIT = "© OpenStreetMap contributors"

export function createViewer(container: HTMLElement): {
  viewer: Cesium.Viewer
  imagery: Cesium.ImageryLayer
} {
  const provider = new Cesium.WebMapServiceImageryProvider({
    url: WMS_URL,
    layers: "osm:osm",
    tileWidth: 512,
    tileHeight: 512,
    credit: new Cesium.Credit(OSM_CREDIT),
  })
  const viewer = new Cesium.Viewer(container, {
    baseLayer: false,
    baseLayerPicker: false,
    animation: false,
    fullscreenButton: false,
    geocoder: false,
    homeButton: false,
    infoBox: false,
    sceneModePicker: false,
    selectionIndicator: false,
    timeline: false,
    navigationHelpButton: false,
    navigationInstructionsInitiallyVisible: false,
    skyBox: false,
    scene3DOnly: true,
    requestRenderMode: true,
    maximumRenderTimeChange: Number.POSITIVE_INFINITY,
  })
  viewer.scene.globe.baseColor = new Cesium.Color(0.05, 0.05, 0.05, 1)
  const imagery = new Cesium.ImageryLayer(provider)
  viewer.imageryLayers.add(imagery)
  return { viewer, imagery }
}
