// Offline bench for the gta4-native SPIR-V loop watchdog: applies
// AddSpirvLoopWatchdog to every .spv file given on the command line and writes
// the guarded module to <out_dir>/<name> for spirv-val.
//
// usage: watchdog_bench <out_dir> <budget> <file.spv>...
#include <cstdio>
#include <filesystem>
#include <fstream>
#include <vector>

#include "native_spirv_loop_watchdog.h"

int main(int argc, char** argv) {
  if (argc < 4) {
    std::fprintf(stderr, "usage: %s <out_dir> <budget> <file.spv>...\n", argv[0]);
    return 2;
  }
  const std::filesystem::path out_dir = argv[1];
  const uint32_t budget = uint32_t(std::stoul(argv[2]));
  std::filesystem::create_directories(out_dir);
  unsigned guarded_shaders = 0, guarded_loops = 0, skipped_loops = 0;
  for (int a = 3; a < argc; ++a) {
    std::ifstream file(argv[a], std::ios::binary);
    std::vector<char> bytes((std::istreambuf_iterator<char>(file)), {});
    std::vector<uint32_t> words(bytes.size() / 4);
    std::memcpy(words.data(), bytes.data(), words.size() * 4);
    auto guarded = rex::graphics::gta4_native::AddSpirvLoopWatchdog(words, budget);
    if (!guarded) continue;
    ++guarded_shaders;
    guarded_loops += guarded->guarded_loops;
    skipped_loops += guarded->skipped_loops;
    std::ofstream out(out_dir / std::filesystem::path(argv[a]).filename(), std::ios::binary);
    out.write(reinterpret_cast<const char*>(guarded->words.data()),
              std::streamsize(guarded->words.size() * 4));
  }
  std::printf("guarded shaders %u, loops %u, skipped loops %u\n", guarded_shaders, guarded_loops,
              skipped_loops);
  return 0;
}
