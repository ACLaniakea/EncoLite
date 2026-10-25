# Third-party notices

## Current Qt client

The current client distributes unmodified CPython 3.13.17 under the Python Software Foundation License and original notices, and dynamically linked Qt / PySide6-Essentials / Shiboken6 6.12.0 from the Qt for Python project's official PyPI wheels. Wheel metadata declares LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only; the open-source licensing options are used. Compatible dynamic libraries can be replaced. Full upstream license texts, third-party notices, source locations and artifact hashes are retained in `licenses/Qt`; original wheel metadata is retained alongside the libraries. Qt and PySide are copyright The Qt Company Ltd. and contributors. Python notices are in `licenses/Python.txt`.

The Qt Quick/QML UI, Python controller and native tray integration are Enco Lite code under GPL-3.0-or-later with the upstream protocol attribution below. No WebView2, Qt WebEngine, Slint, Tk, Avalonia, .NET or PyInstaller binary is included in the current package. Historical implementation notices below do not describe the current runtime. No binary signatures, application-control policies or certificate stores are modified.

The protocol and OPPO/OnePlus model/image attribution below continues to apply. Qt library sources for the exact release are listed in `licenses/Qt/SOURCES.json`; complete application source is provided in the source archive. License files cover each dependency separately; product illustrations are not relicensed as software.

## Historical implementations and shared assets

- **OppoPodsManager**, Copyright © 2026 Zhaoyi-ya, GPL-3.0-or-later. Melody protocol implementation and OPPO model mappings adapted into Python; modifications dated 2026-10-22. Earbud and case PNGs copied from the local upstream project's `Assets/Oplus/Images/official_*.png`; those reference assets retain their original ownership. No endorsement or affiliation with OPPO is implied. Upstream source: https://github.com/Zhaoyi-ya/OppoPodsManager.
- **Slint 1.18.1b1**, Copyright © SixtyFPS GmbH and contributors. Used under its GPL-3.0 option. The project-local runtime includes the package's metadata and software bill of materials. [Slint licensing](https://slint.dev/license.html).
- **CPython 3.12**, Python Software Foundation License and bundled third-party notices. Runtime license is included in the application distribution.
- **PyInstaller 6.16.0**, GPL-2.0-or-later with its bootloader exception. Build tool only; bootloader is distributed under that exception.

Original Enco Lite UI, vector icons, application icon, controller, and native shell integration are provided under GPL-3.0-or-later. The project is supplied without warranty; see LICENSE.

- **OPPO official product images**: 31 model-specific PNG assets obtained from OPPO official product listings on 2026-10-22. Each source URL is retained in `ui/assets/models/manifest.json`. These images remain the property of their respective rights holders and are not relicensed under the software GPL. Their colors are catalog illustrations, not hardware color readback.

- **Native candidate only:** Slint 1.18.0 source is statically linked with a modified PyO3 entry module; the changes and build scripts are in `tools/prepare_native.py` and `native/`. CPython 3.13.17 comes from the Python Software Foundation embeddable distribution, with original signed runtime files unchanged. Exact Rust dependency versions are in `native/Cargo.lock`; corresponding crate source archives and their license files are collected into the candidate source archive. These changes do not imply signing approval or endorsement.

- **OnePlus source update (2026-10-24):** all 32 OnePlus whitelist entries and service/identity metadata are adapted from the same upstream GPL-3.0-or-later catalog. Four official product PNGs (Buds Pro 3, Buds 3, Buds 4 and Nord Buds 3 Pro) are from the specifically named items in OnePlus official product-page navigation. Exact source pages and asset URLs are retained in `ui/assets/models/manifest.json`. Images remain their respective rights holders’ property, retain their original illustration colors, and imply no endorsement or hardware color readback. These source changes are not included in the frozen preview.2 package.
