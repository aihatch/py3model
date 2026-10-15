let { url, apiKey, model, modelPath } = {
    url: "http://localhost:11435/v1",
    apiKey: "",
    model: "qwen3.5",
    // POST /v1/internal/load 需要本地 GGUF 文件绝对路径
    modelPath: ""
}

let execArray = /https*:\/\/([^\/]+)(.+)?/.exec(url)
let hostport = execArray[1].split(":")

module.exports = {
    request: /^https/.test(url) ? "https" : "http",
    hostname: hostport[0],
    port: hostport[1],
    path: execArray[2],
    apiKey,
    model,
    modelPath
}
