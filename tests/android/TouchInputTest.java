package org.callofrecomp;
import java.util.ArrayList;
import java.util.List;

public final class TouchInputTest {
    public static void main(String[] args) {
        List<String> events = new ArrayList<>();
        TouchInput input = new TouchInput((kind, code, x, y) -> events.add(kind+":"+code+":"+x+":"+y));
        input.action("fire", true);
        input.move(-1, -1);
        input.action("reload", true);
        input.releaseAll();
        if (!events.contains("2:1:0:0") || !events.contains("1:4:0:0")
                || !events.contains("1:26:0:0") || !events.contains("1:21:0:0"))
            throw new AssertionError("Hiding controls must release fire, movement and reload together");
        events.clear();
        input.move(1, 0);
        input.move(-1, 0);
        if (!events.equals(java.util.Arrays.asList("1:7:1:0", "1:7:0:0", "1:4:1:0")))
            throw new AssertionError("Changing stick direction must release the previous direction before pressing the next");
        input.releaseAll(); events.clear();
        input.action("aim", true); input.action("aim", true);
        input.action("aim", false); input.action("aim", false);
        if (!events.equals(java.util.Arrays.asList("2:3:1:0", "2:3:0:0")))
            throw new AssertionError("Duplicate action notifications must not leave aiming held");
        events.clear(); input.action("unknown", true);
        if (!events.isEmpty()) throw new AssertionError("Unregistered actions must not inject keys");
        System.out.println("Touch action cancellation and stick transitions passed");
    }
}
