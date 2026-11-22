# Drivux website

A single static page (`index.html`) in English and Turkish, with a light and dark theme.

`python3 site/build.py` builds it into `_site/`:

- **Version:** `{{VERSION}}` in the page is replaced with the current version from `drivux/ortak.py`. When the page loads, it also asks GitHub for the latest release and updates the version, the package file names and the download links. So the site stays right after a release even without a rebuild.
- **Logo:** the logo is copied from the app (`veri/io.github.abdullahnil.Drivux.svg`, `docs/logo.png`), so there is only one logo to keep up to date.

## GitHub Pages

`.github/workflows/site.yml` builds and publishes the site. It runs when the site, the logo or the version changes, and on every new release. In the repository settings, **Pages → Source** must be **GitHub Actions**.

## Cloudflare Pages

In the Cloudflare dashboard, go to **Workers & Pages → Create → Pages → Connect to Git**, choose this repository, and use these settings:

| Setting | Value |
|---|---|
| Production branch | `main` |
| Build command | `python3 site/build.py` |
| Build output directory | `_site` |

Cloudflare then rebuilds the site on every push to `main`.
