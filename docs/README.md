# SML-Cogs

This repo hosts a variety of cogs (aka modules) for use with the **Red Discord Bot** ([source](https://github.com/Twentysix26/Red-DiscordBot) / [documentation](https://twentysix26.github.io/Red-Docs/)). Most of them are in active development and are developed specifically for the **100 Thieves Clan Family** (100T Clash Royale) Discord server.

While some of these cogs can theoretically be used for any Discord server, many contain codes which are 100T-specific.

If you would like to see most of these in action, you can join the RACF Discord server with this invite code: [http://discord.gg/100t](http://discord.gg/100t)

You are welcome to log any issues in the Issues tab, or try to find me on either the RACF Discord server or my own Discord server at [http://discord.me/sml](http://discord.me/sml)

There are no extensive documentation on these cogs. However, usage for many of these commands can be found on the documentation site for the 100T server, since these cogs were mostly written for it: http://docs.100talpha.com

## Notes

The top-level scripts `./enable-cog` and `./disable-cog` were written to help with local cog development and are not needed for the end users. They were made so that cogs can maintain the folder structures expected by the Red bot while making it possible to “install” into the Red folder without using the `cog install` command.

In the production environment, however, you should always install the cogs as specified in the [Installation](#installation) section above.
