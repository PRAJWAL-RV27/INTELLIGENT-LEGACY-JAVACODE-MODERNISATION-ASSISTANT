import java.util.ArrayList;
import java.util.List;

public class TestCollectionEmpty {

    public static void main(String[] args) {

        List<Integer> list = new ArrayList<>();

        for (int i = 0; i < 1000000; i++) {
            list.add(i);
        }

        int count = 0;

        for (int i = 0; i < 10000000; i++) {
            if (list.size() == 0) {
                count++;
            }
        }

        System.out.println(count);
    }
}