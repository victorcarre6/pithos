import { Type } from "@earendil-works/pi-ai";
import { defineTool, type ExtensionAPI } from "@earendil-works/pi-coding-agent";

import { brokerRequest } from "../lib/broker-socket.ts";

const notifyTool = defineTool({
  name: "pithos_notify",
  label: "Pithos Notify",
  description: "Send an allowlisted progress, warning, question or stop proposal to the user.",
  parameters: Type.Object({
    kind: Type.Union([
      Type.Literal("INFO"),
      Type.Literal("WARNING"),
      Type.Literal("QUESTION"),
      Type.Literal("STOP_PROPOSAL"),
      Type.Literal("EMERGENCY"),
    ]),
    text: Type.String({ minLength: 1, maxLength: 3500 }),
  }),

  async execute(toolCallId, params, signal) {
    const socketPath = process.env.PITHOS_TELEGRAM_SOCKET;
    const runId = process.env.PITHOS_RUN_ID;
    if (!socketPath || !runId) {
      throw new Error("PITHOS_TELEGRAM_SOCKET and PITHOS_RUN_ID are required");
    }

    const response = await brokerRequest(
      socketPath,
      {
        request_id: `${runId}-${toolCallId}`,
        run_id: runId,
        kind: params.kind,
        text: params.text,
      },
      signal,
    );
    if (!response.ok) {
      throw new Error(String(response.error ?? "Telegram broker rejected request"));
    }

    return {
      content: [{ type: "text" as const, text: JSON.stringify(response) }],
      details: response,
    };
  },
});

export default function pithosTelegram(pi: ExtensionAPI) {
  pi.registerTool(notifyTool);
}
