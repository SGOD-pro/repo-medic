export interface Env {
  DB: D1Database;
}

export default {
  async fetch(request: Request, env: Env, ctx: ExecutionContext): Promise<Response> {
    return new Response("RepoMedic D1 Worker offline mode", { status: 200 });
  },
};
