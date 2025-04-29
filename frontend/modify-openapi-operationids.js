import * as fs from "node:fs"
import * as http  from "node:http"

async function modifyOpenAPIFile(filePath) {
  try {
    const data = await fs.promises.readFile(filePath)
    const openapiContent = JSON.parse(data)

    const paths = openapiContent.paths
    for (const pathKey of Object.keys(paths)) {
      const pathData = paths[pathKey]
      for (const method of Object.keys(pathData)) {
        const operation = pathData[method]
        if (operation.tags && operation.tags.length > 0) {
          const tag = operation.tags[0]
          const operationId = operation.operationId
          const toRemove = `${tag}-`
          if (operationId.startsWith(toRemove)) {
            const newOperationId = operationId.substring(toRemove.length)
            operation.operationId = newOperationId
          }
        }
      }
    }

    await fs.promises.writeFile(
      filePath,
      JSON.stringify(openapiContent, null, 2),
    )
    console.log("File successfully modified")
  } catch (err) {
    console.error("Error:", err)
  }
}

const filePath = "./openapi.json"

fs.rmSync(filePath, { force: true })

http.get('http://localhost/api/v1/openapi.json', resp => {
  const file = fs.createWriteStream(filePath);
  file.on('finish', () => { modifyOpenAPIFile(filePath); });
  resp.pipe(file);
});

