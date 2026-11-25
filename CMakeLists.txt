cmake_minimum_required(VERSION 3.16)
project(xiapin-input-method VERSION 2.0.5 LANGUAGES CXX)

if(POLICY CMP0167)
    cmake_policy(SET CMP0167 NEW)
endif()

include(GNUInstallDirs)
if(CMAKE_INSTALL_PREFIX_INITIALIZED_TO_DEFAULT)
    set(CMAKE_INSTALL_PREFIX "/usr" CACHE PATH "Install prefix" FORCE)
endif()

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

find_package(PkgConfig REQUIRED)
pkg_check_modules(IBUS REQUIRED IMPORTED_TARGET ibus-1.0)
find_package(Fcitx5Utils REQUIRED)
find_package(LibIMECore REQUIRED)
find_package(LibIMEPinyin REQUIRED)

include(CheckCXXSourceCompiles)
set(CMAKE_REQUIRED_LIBRARIES LibIME::Pinyin)
check_cxx_source_compiles([[ 
#include <libime/pinyin/pinyincontext.h>
int main() {
    auto candidates = &libime::PinyinContext::candidatesToCursor;
    auto select = &libime::PinyinContext::selectCandidatesToCursor;
    (void)candidates;
    (void)select;
    return 0;
}
]] XIAPIN_HAVE_LIBIME_CURSOR_CANDIDATES)
unset(CMAKE_REQUIRED_LIBRARIES)

add_library(xiapin-core STATIC src/engine_core.cpp src/emoji_index.cpp)
target_include_directories(xiapin-core PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/src)
target_link_libraries(xiapin-core PUBLIC LibIME::Pinyin LibIME::Core
    PkgConfig::IBUS)
target_compile_options(xiapin-core PRIVATE -Wall -Wextra -Wpedantic)
if(XIAPIN_HAVE_LIBIME_CURSOR_CANDIDATES)
    target_compile_definitions(xiapin-core PRIVATE
        XIAPIN_HAVE_LIBIME_CURSOR_CANDIDATES=1)
endif()

add_executable(ibus-engine-xiapin src/ibus_engine.cpp)
target_link_libraries(ibus-engine-xiapin PRIVATE xiapin-core PkgConfig::IBUS)
target_compile_options(ibus-engine-xiapin PRIVATE -Wall -Wextra -Wpedantic)
target_compile_definitions(ibus-engine-xiapin PRIVATE
    XIAPIN_DATA_DIR="${CMAKE_INSTALL_FULL_DATADIR}/xiapin")

add_executable(xiapin-history src/history_tool.cpp)
target_link_libraries(xiapin-history PRIVATE LibIME::Core)
target_compile_options(xiapin-history PRIVATE -Wall -Wextra -Wpedantic)

add_executable(xiapin-core-test tests/native-engine-core-test.cpp)
target_link_libraries(xiapin-core-test PRIVATE xiapin-core)

add_executable(xiapin-emoji-index-test tests/emoji-index-test.cpp)
target_link_libraries(xiapin-emoji-index-test PRIVATE xiapin-core)

enable_testing()
add_test(NAME xiapin-core COMMAND xiapin-core-test
    /usr/share/libime/sc.dict
    ${CMAKE_CURRENT_SOURCE_DIR}/data/xiapin-extra.libime-1.0.dict
    /usr/lib/x86_64-linux-gnu/libime/zh_CN.lm
    ${CMAKE_CURRENT_BINARY_DIR}/test-user-data
    /usr/share/ibus/dicts/emoji-zh.dict)
add_test(NAME xiapin-emoji-index COMMAND xiapin-emoji-index-test
    /usr/share/ibus/dicts/emoji-zh.dict)

install(TARGETS ibus-engine-xiapin RUNTIME DESTINATION libexec)
install(TARGETS xiapin-history RUNTIME DESTINATION libexec/xiapin)
install(FILES ibus/xiapin.xml DESTINATION share/ibus/component)
install(FILES ibus/xiapin.xml DESTINATION share/xiapin)
install(FILES data/xiapin-extra.libime-1.0.dict
        DESTINATION share/xiapin RENAME xiapin-extra.dict)
install(FILES icons/xiapin.svg
        DESTINATION share/icons/hicolor/scalable/apps)
