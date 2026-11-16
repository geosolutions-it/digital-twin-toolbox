import { defineConfig } from 'vitepress'

const repo = 'https://github.com/geosolutions-it/digital-twin-toolbox'
const version = process.env.DOCS_VERSION || 'latest'
const base = process.env.DOCS_BASE || '/'

export default defineConfig({
  title: 'Digital Twin Toolbox',
  description: 'Generate 3D Tiles from urban data sources',
  base,
  cleanUrls: true,
  lastUpdated: true,
  head: [['link', { rel: 'icon', href: `${base}logo.svg` }]],
  themeConfig: {
    logo: '/logo.svg',
    version,
    nav: [
      { text: 'Guide', link: '/guide/introduction' },
      { text: 'Development', link: '/development/' },
    ],
    sidebar: [
      {
        text: 'Guide',
        items: [
          { text: 'Introduction', link: '/guide/introduction' },
          { text: 'Getting started', link: '/guide/getting-started' },
          { text: 'The application', link: '/guide/application' },
          { text: 'Jobs and batches', link: '/guide/pipelines' },
          { text: 'Heights', link: '/guide/heights' },
        ],
      },
      {
        text: 'Workflows',
        items: [
          { text: 'Point cloud', link: '/guide/workflows/point-cloud' },
          { text: 'Polygon', link: '/guide/workflows/polygon' },
          { text: 'Point instance', link: '/guide/workflows/point-instance' },
          { text: 'Terrain (experimental)', link: '/guide/workflows/terrain' },
          { text: 'CityGML (experimental)', link: '/guide/workflows/citygml' },
          { text: 'Mesh (experimental)', link: '/guide/workflows/mesh' },
          { text: 'Buildings (experimental)', link: '/guide/workflows/buildings' },
        ],
      },
      {
        text: 'Development',
        items: [
          { text: 'Local stack', link: '/development/' },
          { text: 'Configuration', link: '/development/configuration' },
          { text: 'Backend', link: '/development/backend' },
          { text: 'Frontend', link: '/development/frontend' },
        ],
      },
    ],
    socialLinks: [{ icon: 'github', link: repo }],
    editLink: {
      pattern: `${repo}/edit/main/docs/:path`,
    },
    search: { provider: 'local' },
    footer: {
      message: 'Released under the GPL v3.0 license.',
    },
  },
})
