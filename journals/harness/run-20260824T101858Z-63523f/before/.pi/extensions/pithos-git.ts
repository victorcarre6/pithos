import { Type } from "@earendil-works/pi-ai";
import { defineTool, type ExtensionAPI } from "@earendil-works/pi-coding-agent";

import { brokerRequest } from "../lib/broker-socket.ts";

const gitTool = defineTool({
  name: "pithos_git",
  label: "Pithos Git",
  description: "Manage the current micro-rush through the credential-isolated Git broker.",
  parameters: Type.Object({
    operation: Type.Union([
      Type.Literal("status"),
      Type.Literal("switch"),
      Type.Literal("commit"),
      Type.Literal("push"),
      Type.Literal("pr_create"),
      Type.Literal("pr_view"),
      Type.Literal("pr_merge"),
    ]),
    branch: Type.Optional(Type.String()),
    message: Type.Optional(Type.String()),
    title: Type.Optional(Type.String()),
    body: Type.Optional(Type.String()),
  }),

  async execute(_toolCallId, params, signal) {
    const socketPath = process.env.PITHOS_GIT_SOCKET;
    const runId = process.env.PITHOS_RUN_ID;
    if (!socketPath || !runId) {
      throw new Error("PITHOS_GIT_SOCKET and PITHOS_RUN_ID are required");
    }

    const argumentsByOperation: Record<string, Record<string, unknown>> = {
      status: {},
      switch: { branch: params.branch },
      commit: { message: params.message },
      push: {},
      pr_create: { title: params.title, body: params.body ?? "" },
      pr_view: {},
      pr_merge: {},
    };
    const response = await brokerRequest(
      socketPath,
      {
        run_id: runId,
        operation: params.operation,
        arguments: argumentsByOperation[params.operation],
      },
      signal,
    );
    if (!response.ok) {
      throw new Error(String(response.error ?? "Git broker rejected request"));
    }

    return {
      content: [{ type: "text" as const, text: JSON.stringify(response, null, 2) }],
      details: response,
    };
  },
});

export default function pithosGit(pi: ExtensionAPI) {
  pi.registerTool(gitTool);
}
