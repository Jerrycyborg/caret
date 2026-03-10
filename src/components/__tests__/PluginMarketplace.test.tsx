import { render, screen } from "@testing-library/react";
import PluginMarketplace from "../PluginMarketplace";

jest.mock("@tauri-apps/api/core", () => ({
  invoke: jest.fn().mockResolvedValue([]),
}));

describe("PluginMarketplace", () => {
  it("renders marketplace header", async () => {
    render(<PluginMarketplace />);
    expect(await screen.findByText(/Plugin Marketplace/i)).toBeInTheDocument();
  });
});
