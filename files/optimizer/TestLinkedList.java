import java.util.LinkedList;

public class TestLinkedList {

    public static void main(String[] args) {

        LinkedList<Integer> list = new LinkedList<>();

        for (int i = 0; i < 100000; i++) {
            list.add(i);
        }

        long sum = 0;

        for (int i = 0; i < 100000; i++) {

            if (!list.isEmpty()) {
                sum += list.get(0);
            }
        }

        System.out.println(sum);
    }
}