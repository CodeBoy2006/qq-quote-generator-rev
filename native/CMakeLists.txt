cmake_minimum_required(VERSION 3.15)
project(litehtml_renderer CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

find_package(PkgConfig REQUIRED)
pkg_check_modules(CAIRO REQUIRED cairo)
pkg_check_modules(PANGOCAIRO REQUIRED pangocairo)
pkg_check_modules(HARFBUZZ REQUIRED harfbuzz)
pkg_check_modules(FONTCONFIG REQUIRED fontconfig)
# 尝试通过 pkg-config 找 litehtml
pkg_check_modules(LITEHTML REQUIRED litehtml)

include_directories(
  ${CAIRO_INCLUDE_DIRS}
  ${PANGOCAIRO_INCLUDE_DIRS}
  ${HARFBUZZ_INCLUDE_DIRS}
  ${FONTCONFIG_INCLUDE_DIRS}
  ${LITEHTML_INCLUDE_DIRS}
  ${CMAKE_CURRENT_SOURCE_DIR}
)

link_directories(
  ${CAIRO_LIBRARY_DIRS}
  ${PANGOCAIRO_LIBRARY_DIRS}
  ${HARFBUZZ_LIBRARY_DIRS}
  ${FONTCONFIG_LIBRARY_DIRS}
  ${LITEHTML_LIBRARY_DIRS}
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
  ${LITEHTML_LIBRARIES}
)