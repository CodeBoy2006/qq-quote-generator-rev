cmake_minimum_required(VERSION 3.15)
project(litehtml_renderer CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

find_package(PkgConfig REQUIRED)
pkg_check_modules(CAIRO REQUIRED cairo)
pkg_check_modules(PANGOCAIRO REQUIRED pangocairo)
pkg_check_modules(HARFBUZZ REQUIRED harfbuzz)
pkg_check_modules(FONTCONFIG REQUIRED fontconfig)

# --- CHANGED ---
# We no longer use pkg-config for litehtml.
# find_package can find libraries installed from source.
find_package(litehtml REQUIRED)
# ---------------

include_directories(
  ${CAIRO_INCLUDE_DIRS}
  ${PANGOCAIRO_INCLUDE_DIRS}
  ${HARFBUZZ_INCLUDE_DIRS}
  ${FONTCONFIG_INCLUDE_DIRS}
  # The find_package command sets litehtml_INCLUDE_DIRS
  ${litehtml_INCLUDE_DIRS}
  ${CMAKE_CURRENT_SOURCE_DIR}
)

# link_directories is often not needed if find_package is used correctly,
# but we'll keep it for robustness.
link_directories(
  ${CAIRO_LIBRARY_DIRS}
  ${PANGOCAIRO_LIBRARY_DIRS}
  ${HARFBUZZ_LIBRARY_DIRS}
  ${FONTCONFIG_LIBRARY_DIRS}
  # The find_package command sets litehtml_LIBRARY_DIRS
  ${litehtml_LIBRARY_DIRS}
)

add_executable(litehtml_renderer
  main.cpp
  container_pango_cairo.cpp
)

target_link_libraries(litehtml_renderer
  ${CAIRO_LIBRARIES}
  ${PANGOCAIRO_LIBRARIES}
  ${HARFBUZZ_LIBRARIES}
  ${FONTCONFIG_LIBRARIES}
  # The find_package command sets litehtml_LIBRARIES
  ${litehtml_LIBRARIES}
)