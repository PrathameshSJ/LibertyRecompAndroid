#pragma once
// Bounds every structured loop of a recompiled shader by a per-invocation
// iteration budget. Xenos loops use 8-bit counters, so a legitimate shader never
// comes close to the budget; a loop that does (stale constants, NaN-driven
// predicates in the control-flow state machine) ends the invocation instead of
// running until the kernel resets the GPU.
//
// Each void function gets one Function-storage counter, bumped once per
// iteration. The rewrite keeps the module structured (spirv-val clean); a loop
// header may only end in OpBranchConditional when one target is its merge
// block, so the budget test never becomes the header's own branch:
//
// * Header ending in `OpBranch %body`: the header branches to a new guard
//   block instead, which counts the iteration and is a proper selection,
//     OpSelectionMerge %body
//     OpBranchConditional %ok %body %expired      ; %expired: OpReturn
//   Returning is a legal exit from the selection, no edge is added to the loop
//   merge (values leaving the loop by dominance stay valid), and %body's OpPhis
//   name the guard as their predecessor.
// * Header ending in `OpBranchConditional %c %t %f` with %t or %f the merge
//   block: the condition is widened in place so an exhausted budget takes that
//   exit (%c || !%ok, or %c && %ok). No block or edge is added.
// * Anything else (including a header that is its own continue target) is
//   left unguarded and reported in skipped_loops.
#include <cstdint>
#include <optional>
#include <unordered_map>
#include <vector>

namespace rex::graphics::gta4_native {

struct SpirvLoopWatchdogResult {
  std::vector<uint32_t> words;
  uint32_t guarded_loops = 0;
  uint32_t skipped_loops = 0;
};

inline std::optional<SpirvLoopWatchdogResult> AddSpirvLoopWatchdog(const std::vector<uint32_t>& in,
                                                                   uint32_t budget) {
  constexpr uint16_t kOpTypeVoid = 19, kOpTypeBool = 20, kOpTypeInt = 21, kOpTypePointer = 32,
                     kOpConstant = 43, kOpFunction = 54, kOpFunctionEnd = 56, kOpVariable = 59,
                     kOpLoad = 61, kOpStore = 62, kOpLabel = 248, kOpBranch = 249,
                     kOpBranchConditional = 250, kOpLoopMerge = 246, kOpSelectionMerge = 247,
                     kOpReturn = 253, kOpIAdd = 128, kOpULessThan = 176, kOpLogicalOr = 166,
                     kOpLogicalAnd = 167, kOpLogicalNot = 168, kOpPhi = 245;
  constexpr uint32_t kStorageFunction = 7, kSelectionControlNone = 0;
  if (in.size() < 5 || in[0] != 0x07230203u) return std::nullopt;

  enum class Kind { kGuardBlock, kWidenTrueExit, kWidenFalseExit };
  struct Guard {
    Kind kind;
    uint32_t guard_label = 0;  // kGuardBlock only
  };

  uint32_t bound = in[3];
  uint32_t uint_type = 0, bool_type = 0, uint_function_pointer = 0, void_type = 0;
  size_t first_function = 0;
  struct Rename {
    uint32_t header, guard;
  };
  // Loop bodies entered through a new guard block: their OpPhis name the guard.
  std::unordered_map<uint32_t, Rename> phi_renames;
  std::unordered_map<size_t, Guard> guards;  // OpLoopMerge word index -> rewrite
  uint32_t skipped = 0;
  bool void_function = false;
  uint32_t current_label = 0;
  for (size_t i = 5; i < in.size();) {
    const uint32_t count = in[i] >> 16;
    const uint16_t op = uint16_t(in[i] & 0xFFFF);
    if (!count || i + count > in.size()) return std::nullopt;
    const uint32_t* w = in.data() + i;
    if (op == kOpTypeVoid) void_type = w[1];
    if (op == kOpTypeInt && w[2] == 32 && w[3] == 0 && !uint_type) uint_type = w[1];
    if (op == kOpTypeBool && !bool_type) bool_type = w[1];
    if (op == kOpTypePointer && w[2] == kStorageFunction && w[3] == uint_type && uint_type)
      uint_function_pointer = w[1];
    if (op == kOpFunction) {
      if (!first_function) first_function = i;
      void_function = void_type && w[1] == void_type;
    }
    if (op == kOpLabel) current_label = w[1];
    if (op == kOpLoopMerge && i + count < in.size()) {
      const uint32_t merge = w[1], continue_target = w[2];
      const uint32_t* t = in.data() + i + count;
      const uint16_t t_op = uint16_t(t[0] & 0xFFFF);
      bool guarded = false;
      // A header that is its own continue target belongs to the continue
      // construct, where neither a guard block nor a returning block fits.
      if (void_function && continue_target != current_label) {
        if (t_op == kOpBranch && t[1] != merge && t[1] != continue_target &&
            !phi_renames.count(t[1])) {
          const uint32_t guard = bound++;
          guards[i] = {Kind::kGuardBlock, guard};
          phi_renames[t[1]] = {current_label, guard};
          guarded = true;
        } else if (t_op == kOpBranchConditional && t[2] != t[3] &&
                   (t[2] == merge || t[3] == merge)) {
          guards[i] = {t[2] == merge ? Kind::kWidenTrueExit : Kind::kWidenFalseExit};
          guarded = true;
        }
      }
      if (!guarded) ++skipped;
    }
    i += count;
  }
  if (guards.empty() || !first_function) return std::nullopt;

  std::vector<uint32_t> globals;
  auto emit_to = [](std::vector<uint32_t>& out, uint16_t op, std::initializer_list<uint32_t> operands) {
    out.push_back(uint32_t(operands.size() + 1) << 16 | op);
    out.insert(out.end(), operands);
  };
  if (!uint_type) {
    uint_type = bound++;
    emit_to(globals, kOpTypeInt, {uint_type, 32, 0});
  }
  if (!bool_type) {
    bool_type = bound++;
    emit_to(globals, kOpTypeBool, {bool_type});
  }
  if (!uint_function_pointer) {
    uint_function_pointer = bound++;
    emit_to(globals, kOpTypePointer, {uint_function_pointer, kStorageFunction, uint_type});
  }
  const uint32_t zero = bound++, one = bound++, limit = bound++;
  emit_to(globals, kOpConstant, {uint_type, zero, 0});
  emit_to(globals, kOpConstant, {uint_type, one, 1});
  emit_to(globals, kOpConstant, {uint_type, limit, budget});

  SpirvLoopWatchdogResult result;
  result.skipped_loops = skipped;
  std::vector<uint32_t>& out = result.words;
  out.reserve(in.size() + in.size() / 6 + globals.size() + 64);
  out.insert(out.end(), in.begin(), in.begin() + 5);

  uint32_t counter = 0;
  bool in_function = false, first_block = false, counter_initialized = false;
  // Counts one iteration; returns the id of `counter < budget` after the bump.
  const auto emit_count = [&]() {
    const uint32_t value = bound++, next = bound++, ok = bound++;
    emit_to(out, kOpLoad, {uint_type, value, counter});
    emit_to(out, kOpIAdd, {uint_type, next, value, one});
    emit_to(out, kOpStore, {counter, next});
    emit_to(out, kOpULessThan, {bool_type, ok, next, limit});
    return ok;
  };
  current_label = 0;
  for (size_t i = 5; i < in.size();) {
    const uint32_t count = in[i] >> 16;
    const uint16_t op = uint16_t(in[i] & 0xFFFF);
    const uint32_t* w = in.data() + i;
    if (i == first_function) out.insert(out.end(), globals.begin(), globals.end());

    if (op == kOpFunction) {
      in_function = true;
      first_block = counter_initialized = false;
      counter = 0;
    } else if (op == kOpFunctionEnd) {
      in_function = false;
    }
    // The counter joins the first block's leading OpVariables and is zeroed
    // right after them.
    if (in_function && first_block && !counter_initialized && op != kOpVariable) {
      emit_to(out, kOpStore, {counter, zero});
      counter_initialized = true;
      first_block = false;
    }

    if (op == kOpLoopMerge && counter) {
      if (const auto found = guards.find(i); found != guards.end()) {
        const Guard& guard = found->second;
        const uint32_t* t = in.data() + i + count;
        const uint32_t t_count = t[0] >> 16;
        if (guard.kind == Kind::kGuardBlock) {
          const uint32_t body = t[1], expired = bound++;
          out.insert(out.end(), w, w + count);  // OpLoopMerge
          emit_to(out, kOpBranch, {guard.guard_label});
          emit_to(out, kOpLabel, {guard.guard_label});
          const uint32_t ok = emit_count();
          emit_to(out, kOpSelectionMerge, {body, kSelectionControlNone});
          emit_to(out, kOpBranchConditional, {ok, body, expired});
          emit_to(out, kOpLabel, {expired});
          out.push_back(uint32_t(1) << 16 | kOpReturn);
        } else {
          const uint32_t ok = emit_count();
          const uint32_t widened = bound++;
          if (guard.kind == Kind::kWidenTrueExit) {
            const uint32_t expired = bound++;
            emit_to(out, kOpLogicalNot, {bool_type, expired, ok});
            emit_to(out, kOpLogicalOr, {bool_type, widened, t[1], expired});
          } else {
            emit_to(out, kOpLogicalAnd, {bool_type, widened, t[1], ok});
          }
          out.insert(out.end(), w, w + count);  // OpLoopMerge
          const size_t branch = out.size();
          out.insert(out.end(), t, t + t_count);  // keeps any branch weights
          out[branch + 1] = widened;
        }
        ++result.guarded_loops;
        i += count + t_count;
        continue;
      }
    }

    if (op == kOpLabel) current_label = w[1];
    if (op == kOpPhi) {
      if (const auto rename = phi_renames.find(current_label); rename != phi_renames.end()) {
        const size_t start = out.size();
        out.insert(out.end(), w, w + count);
        for (size_t parent = start + 4; parent < out.size(); parent += 2)
          if (out[parent] == rename->second.header) out[parent] = rename->second.guard;
        i += count;
        continue;
      }
    }
    out.insert(out.end(), w, w + count);

    if (op == kOpLabel && in_function && !counter) {
      counter = bound++;
      emit_to(out, kOpVariable, {uint_function_pointer, counter, kStorageFunction});
      first_block = true;
    }
    i += count;
  }
  if (!result.guarded_loops) return std::nullopt;
  out[3] = bound;
  return result;
}

}  // namespace rex::graphics::gta4_native
