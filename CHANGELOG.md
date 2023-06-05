# Changelog

## [Unreleased]

## [2.13] - 2023-06-05

### Added

- WG-13 update python-client and add example used in load testing (#125)

### Changed

- Use ubuntu-latest in CI testing (#124)

### Fixed

- WG-66 and WG-36: fix path to mapillary tools and refactor error handling for streetview files (#126)


## [2.12] - 2023-04-11

### Fixed
- DES-2420: fix handling of missing image geolocation

## [2.11] - 2023-03-02

### Fixed
- DES-2381: fix errors related to determining if a user can delete a project (#111)

### Changed
- Move project asset directory deletion work to celery task (#118)
- Add status endpoint (#117)

## [2.10] - 2023-01-04

### Fixed
- DES-2374: fix service account url for getting files (#108)
- DES-2213: update dependencies (#97)

## [2.9] - 2022-09-29

### Added

- DES-2231: handle potential listing errors (#105)
- Add util image (#102)
- Use env file for docker compose (#101)
- DES-1996: Restrict project deletion (#100)
- DES-2236: Add retry attempts to file getting (#99)

### Fixed

- Hotfix: Project deletion (#104)

## [2.8] - 2022-06-03

### Changed
- DES-2216: Use description for point cloud asset name instead of ID (#89)
- DES-2211: Increase memory limit for worker pods (#93)

### Fixed
- DES-2262: use github actions for unit testing (#91)

## [2.7] - 2022-04-27

### Added
- DES-1828: Add Streetview support through Mapillary (#46)
- DES-2240: Test for access to streetview (#85)

## [2.6] - 2022-04-19

### Added
- DES-2198: Update periodic importing of files to avoid importing files that had previously failed (#81)

### Changed
- DES-2185: Fix filtering query (#76)

### Fixed
- DES-2195 fix tests for project service (#81)


## [2.5] - 2022-03-07

### Changed
- DES-2177: do not scrape files in .Trash folder (#77)

### Fixed
- DES-2176: fix failed importing of some images (#75)
- Transition to larger volume for /assets (#78)

## [2.4] - 2022-01-21

### Changed
- DES-2003: Update prod deployment to use new PG data claim. (#63)
- DES-2001: Project links as observables (subscribe to project-user data). (#65)
- DES-1988: Delete saving file on export. (#68)

### Fixed
- DES-2000: Fix travis-ci builds. (#62)
- DES-2084: Use service account to download file. (#72)

## [2.3] - 2021-06-09

### Added
- DES-1929: Implement saving project to hazmapper (#54)

### Changed
- DES-1950: Update deployment (#57)

### Fixed
- Fix observable project import. (#60)

## [2.2] - 2021-04-28

### Added
- DES-1676: Add update functionality to individual projects. (#39)
- DES-1946: Provide public routes (#56)
- DES-1788: Support public maps (#40)
- DES-1788: Support public maps for new and missing routes (#53)
- DES-1760: Add Tile Servers Backend (#42)
- DES-1899: Support querying projects by UUID (#50)

### Changed
- DES-1713: Deploy images to Docker Hub tagged by git hash(#44)
- DES-1728: Improve tapis file access related logging (#32)
- DES-1713: Update kube for staging (#45)

### Fixed
- DES-1853: Fix imporing of RAPP folders (#32)

## [2.1] - 2020-10-05

### Added
- DES-350: Add shapefile support (#37)

### Changed
- DES-1532: Add users automatically to projects (#34)
- DES-1730: Extend getBoundingBox to use z coordinate (#33)

### Fixed
- DES-1687: Add rollingback to worker tasks (#30)
- DES-1663: Fix image rotations (#36)

[unreleased]: https://github.com/TACC-Cloud/geoapi/compare/v2.13...HEAD
[2.13]: https://github.com/TACC-Cloud/geoapi/releases/tag/v2.13
[2.12]: https://github.com/TACC-Cloud/geoapi/releases/tag/v2.12
[2.11]: https://github.com/TACC-Cloud/geoapi/releases/tag/v2.11
[2.9]: https://github.com/TACC-Cloud/geoapi/releases/tag/v2.9
[2.8]: https://github.com/TACC-Cloud/geoapi/releases/tag/v2.8
[2.7]: https://github.com/TACC-Cloud/geoapi/releases/tag/v2.7
[2.6]: https://github.com/TACC-Cloud/geoapi/releases/tag/v2.6
[2.5]: https://github.com/TACC-Cloud/geoapi/releases/tag/v2.5
[2.4]: https://github.com/TACC-Cloud/geoapi/releases/tag/v2.4
[2.3]: https://github.com/TACC-Cloud/geoapi/releases/tag/v2.3
[2.2]: https://github.com/TACC-Cloud/geoapi/releases/tag/v2.2
[2.1]: https://github.com/TACC-Cloud/geoapi/releases/tag/v2.1
