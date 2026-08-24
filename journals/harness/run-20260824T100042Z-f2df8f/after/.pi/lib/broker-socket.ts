import net from "node:net";

export function brokerRequest(
  socketPath: string,
  payload: unknown,
  signal: AbortSignal,
): Promise<Record<string, unknown>> {
  return new Promise((resolve, reject) => {
    const socket = net.createConnection(socketPath);
    let buffer = "";

    const fail = (reason: Error) => {
      socket.destroy();
      reject(reason);
    };
    const abort = () => fail(new Error("Broker request aborted"));
    signal.addEventListener("abort", abort, { once: true });
    socket.setTimeout(10_000, () => fail(new Error("Broker request timed out")));
    socket.on("error", fail);
    socket.on("connect", () => {
      socket.write(`${JSON.stringify(payload)}\n`);
    });
    socket.on("data", (chunk) => {
      buffer += chunk.toString("utf8");
      const newline = buffer.indexOf("\n");
      if (newline < 0) return;

      signal.removeEventListener("abort", abort);
      socket.end();
      try {
        resolve(JSON.parse(buffer.slice(0, newline)) as Record<string, unknown>);
      } catch {
        reject(new Error("Broker returned invalid JSON"));
      }
    });
  });
}
