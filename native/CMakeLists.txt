cmake_minimum_required(VERSION 3.15)
project(litehtml_renderer CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Dependencies via pkg-config
find_package(PkgConfig REQUIRED)
pkg_check_modules(CAIRO REQUIRED cairo)
pkg_check_modules(PANGOCAIRO REQUIRED pangocairo)
pkg_check_modules(HARFBUZZ REQUIRED harfbuzz)
pkg_check_modules(FONTCONFIG REQUIRED fontconfig)

# ---- Use the exact litehtml we just built in /opt/litehtml ----
if (NOT DEFINED LITEHTML_DIR)
  message(FATAL_ERROR "LITEHTML_DIR not set (pass -DLITEHTML_DIR=/opt/litehtml)")
endif()

set(LITEHTML_INCLUDE_DIR "${LITEHTML_DIR}/include")
set(LITEHTML_STATIC_LIB  "${LITEHTML_DIR}/build/liblitehtml.a")

if (NOT EXISTS "${LITEHTML_STATIC_LIB}")
  message(FATAL_ERROR "liblitehtml.a not found at ${LITEHTML_STATIC_LIB}")
endif()

add_library(litehtml STATIC IMPORTED GLOBAL)
set_target_properties(litehtml PROPERTIES
  IMPORTED_LOCATION "${LITEHTML_STATIC_LIB}"
  INTERFACE_INCLUDE_DIRECTORIES "${LITEHTML_INCLUDE_DIR}"
)

add_executable(litehtml_renderer
  main.cpp
  container_pango_cairo.cpp
)

target_include_directories(litehtml_renderer PRIVATE
  ${LITEHTML_INCLUDE_DIR}
  ${CAIRO_INCLUDE_DIRS}
  ${PANGOCAIRO_INCLUDE_DIRS}
  ${HARFBUZZ_INCLUDE_DIRS}
  ${FONTCONFIG_INCLUDE_DIRS}
  ${CMAKE_CURRENT_SOURCE_DIR}
)

target_link_libraries(litehtml_renderer
  litehtml
  ${CAIRO_LIBRARIES}
  ${PANGOCAIRO_LIBRARIES}
  ${HARFBUZZ_LIBRARIES}
  ${FONTCONFIG_LIBRARIES}
)

# Consistent UTF-8 build
target_compile_definitions(litehtml_renderer PRIVATE LITEHTML_UTF8=1)