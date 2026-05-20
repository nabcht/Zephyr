# Terms of Service

Last Updated: May 18, 2026

By using Zephyr, you agree to the following terms.

## Use of Software

Zephyr is provided as an open-source tool for personal and professional use. You are responsible for the environment in which it is deployed and the data it can access.

## AI Output Disclaimer

Zephyr interfaces with local or remote large language model providers. Generated content, tool plans, and mission outputs are not guaranteed to be accurate, safe, or reliable without operator review.

## Responsibility for Actions

If `REQUIRE_CONFIRMATION` is disabled, the runtime may execute local commands, file actions, or integration-backed actions without an extra approval step. You accept responsibility for any resulting data loss, system damage, or unintended side effects.

## External Integrations And Data Flow

If you enable remote inference providers or external subprocess integrations such as MCP servers, you are responsible for understanding the data that may leave the local machine and the trust boundary those services introduce.

## Local-Host Assumption

The shipped backend is intended for local-host use. If you expose it beyond your machine, you are responsible for adding your own authentication, network controls, and reverse-proxy protections.

## Limitation of Liability

The software is provided as-is without warranty of any kind. In no event shall the authors or contributors be liable for claims, damages, or other liability arising from use of the software.

## License

Usage remains governed by the MIT License included in this repository.