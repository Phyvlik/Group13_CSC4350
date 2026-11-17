import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { API_URL, ApiError, http, setToken } from "./http";

const fetchMock = vi.fn();

function reply(status: number, body: unknown) {
  return Promise.resolve(new Response(status === 204 ? null : JSON.stringify(body), { status }));
}

beforeEach(() => {
  vi.stubGlobal("fetch", fetchMock);
  localStorage.clear();
});

afterEach(() => {
  vi.unstubAllGlobals();
  fetchMock.mockReset();
});

describe("api http helper", () => {
  it("sends the stored token as a Bearer header", async () => {
    setToken("abc.def.ghi");
    fetchMock.mockReturnValue(reply(200, []));

    await http.get("/sessions");

    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe(`${API_URL}/sessions`);
    expect(init.headers.Authorization).toBe("Bearer abc.def.ghi");
  });

  it("sends no Authorization header when signed out", async () => {
    fetchMock.mockReturnValue(reply(200, []));

    await http.get("/datasets");

    expect(fetchMock.mock.calls[0][1].headers.Authorization).toBeUndefined();
  });

  it("sends JSON bodies", async () => {
    setToken("t");
    fetchMock.mockReturnValue(reply(201, { ok: true }));

    await http.post("/sessions/1/trades", { side: "BUY", quantity: "5" });

    const init = fetchMock.mock.calls[0][1];
    expect(init.method).toBe("POST");
    expect(init.headers["Content-Type"]).toBe("application/json");
    expect(JSON.parse(init.body)).toEqual({ side: "BUY", quantity: "5" });
  });

  it("turns error responses into an ApiError with the server's detail", async () => {
    fetchMock.mockReturnValue(reply(409, { detail: "Dataset is in use" }));

    const error = await http.delete("/admin/datasets/1").catch((x: unknown) => x);

    expect(error).toBeInstanceOf(ApiError);
    expect((error as ApiError).status).toBe(409);
    expect((error as ApiError).message).toBe("Dataset is in use");
  });

  it("reads the first message from a validation error list", async () => {
    fetchMock.mockReturnValue(reply(422, { detail: [{ msg: "Value error, start must be earlier than end" }] }));

    await expect(http.post("/x", {})).rejects.toThrow("start must be earlier than end");
  });

  it("reports an unreachable server", async () => {
    fetchMock.mockRejectedValue(new TypeError("Failed to fetch"));

    await expect(http.get("/health")).rejects.toThrow("Could not reach the server.");
  });

  it("returns undefined for 204 No Content", async () => {
    fetchMock.mockReturnValue(reply(204, null));

    await expect(http.delete("/admin/datasets/1")).resolves.toBeUndefined();
  });
});
