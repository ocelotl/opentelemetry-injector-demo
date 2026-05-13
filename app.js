const http = require("http");

const server = http.createServer((req, res) => {
  console.log("received request");

  res.end("hello from otel injector\n");
});

server.listen(3000, () => {
  console.log("listening on port 3000");
});
