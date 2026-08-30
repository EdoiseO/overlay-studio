# Bundled Font Licenses

Overlay Studio bundles the following Google Fonts so overlays keep their chosen
typography without an internet connection and PNG exports can render the exact
same glyphs as OBS:

- Anton
- Archivo Black
- Fredoka
- Montserrat
- Nunito
- Poppins

Each family is distributed under the SIL Open Font License 1.1. Its family-specific
license text is stored beside this file as `<family>-OFL.txt`.

The WOFF2 files and `overlay-fonts.css` were retrieved from the official Google
Fonts CSS service on 2026-08-15. Source metadata and upstream font files are
maintained in the [Google Fonts repository](https://github.com/google/fonts).

Pixel Clock Line, Pixel Countdown Line, Pixel Stopwatch Line, Block Beats,
and Pixel Now Playing use the regular and bold faces from Idrees Hassan's
[Minecraft-Font](https://github.com/IdreesInc/Minecraft-Font) project. The exact
source revision is commit `261ac77fbf28796ca09c22eb83ecdfe386c4b838`, retrieved
on 2026-08-30. The repository's root `LICENSE` file is the authoritative SIL Open
Font License 1.1 text and is copied verbatim to `pixel-ui-OFL.txt`. It does not
declare a Reserved Font Name.

The upstream `Minecraft.otf` and `Minecraft-Bold.otf` files were converted without
subsetting to WOFF2 with fontTools. The OTF sources are not distributed here. CSS
exposes the converted files under the neutral `Pixel UI` family alias:

- `PixelUI-Regular.woff2` — SHA-256 `E724F938ACBBF143A64E487960ED195B1D5581BDF59872673D95F07A9B805657`
- `PixelUI-Bold.woff2` — SHA-256 `31EDDA90BCDD1C4B1BAD745C5A7476680D79A0D0AAFA2A1B09C3DC25EF8D07DC`
- `pixel-ui-OFL.txt` — SHA-256 `7BA264D7239B5961117452883FF54A37EEA7001B90354B767F24948FA655B558`

The upstream project describes itself as an unaffiliated fan project that emulates
the typeface without including assets or font files from the original game.
